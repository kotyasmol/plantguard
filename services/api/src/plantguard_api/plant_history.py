from __future__ import annotations

import time
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from plantguard_mining import (
    SPECIES_CATALOG,
    AssessmentSignals,
    ExplanationContext,
    GroundedExplanationGenerator,
    IdentificationCandidate,
    OverallTrend,
    RiskLevel,
    calculate_dynamics,
    evaluate,
)
from plantguard_mining.ports import (
    ImageReference,
    PhotoComparator,
    PlantIdentifier,
    SymptomExtractor,
    VisualConditionAnalyzer,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .config import Settings, get_settings
from .database import Assessment as AssessmentRecord
from .database import CareEvent, Observation, Photo, Plant, User, get_session
from .dependencies import (
    get_explanation_generator,
    get_photo_comparator,
    get_photo_link_signer,
    get_photo_storage,
    get_plant_identifier,
    get_symptom_extractor,
    get_visual_condition_analyzer,
)
from .events import IdentificationCandidate as EventCandidate
from .events import (
    build_assessment_event,
    build_care_event,
    build_identification_event,
    build_observation_event,
)
from .outbox import enqueue_event
from .photo_links import PhotoLinkSigner
from .photo_storage import PhotoStorage
from .photo_validation import PhotoValidationError, validate_photo_upload
from .schemas import (
    CareEventCreate,
    CareEventResult,
    DecisionAssessmentResult,
    DecisionEvidenceResult,
    FindingChangeResult,
    IdentificationResult,
    ObservationDynamicsResult,
    ObservationResult,
    PhotoComparisonResult,
    PhotoResult,
    PlantCreate,
    PlantHistoryResult,
    PlantResult,
    PlantSpeciesUpdate,
    SpeciesCandidateResult,
    StoredAssessmentResult,
    TextAnalysisResult,
    TextFindingResult,
    VisualAnalysisResult,
    VisualFindingResult,
)
from .security import get_current_user

router = APIRouter(prefix="/api/v1/plants", tags=["plants"])


def candidate_names(candidate: IdentificationCandidate) -> tuple[str, str]:
    local_species = SPECIES_CATALOG.get(candidate.species_code)
    scientific_name = candidate.scientific_name or (
        local_species.scientific_name if local_species else candidate.display_name
    )
    common_name = candidate.common_name or (
        local_species.common_name if local_species else candidate.display_name
    )
    return scientific_name, common_name


def require_plant(session: Session, plant_id: UUID, owner_id: UUID) -> Plant:
    plant = session.scalar(
        select(Plant).where(Plant.id == plant_id, Plant.owner_id == owner_id)
    )
    if plant is None:
        raise HTTPException(status_code=404, detail="Растение не найдено")
    return plant


def require_observation(
    session: Session,
    plant_id: UUID,
    observation_id: UUID,
    owner_id: UUID,
) -> Observation:
    observation = session.scalar(
        select(Observation)
        .join(Observation.plant)
        .where(
            Observation.id == observation_id,
            Observation.plant_id == plant_id,
            Plant.owner_id == owner_id,
        )
        .options(selectinload(Observation.photos))
    )
    if observation is None:
        raise HTTPException(status_code=404, detail="Наблюдение не найдено")
    return observation


def photo_result(
    request: Request,
    photo: Photo,
    signer: PhotoLinkSigner,
    configuration: Settings,
) -> PhotoResult:
    expires = int(time.time()) + configuration.photo_url_ttl_seconds
    signature = signer.sign("GET", photo.storage_key, expires)
    url = request.url_for("download_photo", storage_key=photo.storage_key)
    return PhotoResult(
        id=photo.id,
        storage_key=photo.storage_key,
        original_filename=photo.original_filename,
        media_type=photo.media_type,
        size_bytes=photo.size_bytes,
        checksum_sha256=photo.checksum_sha256,
        read_url=str(url.include_query_params(expires=expires, signature=signature)),
    )


def observation_result(
    request: Request,
    observation: Observation,
    signer: PhotoLinkSigner,
    configuration: Settings,
) -> ObservationResult:
    return ObservationResult(
        id=observation.id,
        plant_id=observation.plant_id,
        description=observation.description,
        humidity_pct=float(observation.humidity_pct)
        if observation.humidity_pct is not None
        else None,
        temperature_c=float(observation.temperature_c)
        if observation.temperature_c is not None
        else None,
        observed_at=observation.observed_at,
        created_at=observation.created_at,
        photos=[
            photo_result(request, photo, signer, configuration)
            for photo in observation.photos
        ],
    )


@router.post("", response_model=PlantResult, status_code=status.HTTP_201_CREATED)
def create_plant(
    payload: PlantCreate,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Plant:
    plant = Plant(owner_id=current_user.id, **payload.model_dump())
    session.add(plant)
    session.commit()
    session.refresh(plant)
    return plant


@router.get("", response_model=list[PlantResult])
def list_plants(
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[Plant]:
    return list(
        session.scalars(
            select(Plant)
            .where(Plant.owner_id == current_user.id)
            .order_by(Plant.updated_at.desc())
        ).all()
    )


@router.get("/{plant_id}", response_model=PlantResult)
def get_plant(
    plant_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Plant:
    return require_plant(session, plant_id, current_user.id)


@router.patch("/{plant_id}/species", response_model=PlantResult)
def confirm_plant_species(
    plant_id: UUID,
    payload: PlantSpeciesUpdate,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Plant:
    plant = require_plant(session, plant_id, current_user.id)
    plant.species_scientific_name = payload.scientific_name
    plant.species_common_name = payload.common_name
    plant.species_status = "confirmed"
    session.commit()
    session.refresh(plant)
    return plant


@router.post(
    "/{plant_id}/observations",
    response_model=ObservationResult,
    status_code=status.HTTP_201_CREATED,
)
async def create_observation(
    request: Request,
    plant_id: UUID,
    photo: Annotated[UploadFile, File()],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
    signer: Annotated[PhotoLinkSigner, Depends(get_photo_link_signer)],
    configuration: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[User, Depends(get_current_user)],
    description: Annotated[Optional[str], Form()] = None,
    humidity_pct: Annotated[Optional[float], Form()] = None,
    temperature_c: Annotated[Optional[float], Form()] = None,
    observed_at: Annotated[Optional[datetime], Form()] = None,
) -> ObservationResult:
    require_plant(session, plant_id, current_user.id)
    try:
        validated = await validate_photo_upload(
            photo,
            max_bytes=configuration.max_image_bytes,
            max_pixels=configuration.max_image_pixels,
        )
    except PhotoValidationError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    if humidity_pct is not None and not 0 <= humidity_pct <= 100:
        raise HTTPException(status_code=422, detail="Влажность должна быть от 0 до 100")
    if temperature_c is not None and not -50 <= temperature_c <= 70:
        raise HTTPException(
            status_code=422,
            detail="Температура находится вне допустимого диапазона",
        )

    stored = storage.save(validated.content, validated.media_type)
    observation = Observation(
        plant_id=plant_id,
        description=description,
        humidity_pct=Decimal(str(humidity_pct)) if humidity_pct is not None else None,
        temperature_c=Decimal(str(temperature_c)) if temperature_c is not None else None,
    )
    if observed_at is not None:
        observation.observed_at = observed_at
    observation.photos.append(
        Photo(
            storage_key=stored.storage_key,
            original_filename=photo.filename or "photo",
            media_type=validated.media_type,
            size_bytes=stored.size_bytes,
            checksum_sha256=stored.checksum_sha256,
        )
    )
    session.add(observation)
    try:
        session.flush()
        enqueue_event(
            session,
            topic="plant.observations.v1",
            event=build_observation_event(
                observation_id=observation.id,
                plant_id=observation.plant_id,
                storage_key=observation.photos[0].storage_key,
                observed_at=observation.observed_at,
                description=observation.description,
                humidity_pct=observation.humidity_pct,
                temperature_c=observation.temperature_c,
            ),
        )
        session.commit()
        session.refresh(observation)
    except Exception:
        session.rollback()
        storage.delete(stored.storage_key)
        raise
    return observation_result(request, observation, signer, configuration)


@router.post(
    "/{plant_id}/observations/{observation_id}/identify",
    response_model=IdentificationResult,
)
def identify_observation(
    plant_id: UUID,
    observation_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
    identifier: Annotated[PlantIdentifier, Depends(get_plant_identifier)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> IdentificationResult:
    plant = require_plant(session, plant_id, current_user.id)
    observation = require_observation(session, plant_id, observation_id, current_user.id)
    if not observation.photos:
        raise HTTPException(status_code=409, detail="У наблюдения нет фотографии")
    photo = storage.locate(observation.photos[0].storage_key)
    outcome = identifier.identify(
        ImageReference(uri=str(photo.path), media_type=photo.media_type)
    )
    candidates = []
    for candidate in outcome.candidates:
        scientific_name, common_name = candidate_names(candidate)
        candidates.append(
            SpeciesCandidateResult(
                species_code=candidate.species_code,
                scientific_name=scientific_name,
                common_name=common_name,
                confidence=candidate.confidence,
            )
        )
    if outcome.recognized:
        top = candidates[0]
        plant.species_scientific_name = top.scientific_name
        plant.species_common_name = top.common_name
        plant.species_status = "suggested"
    enqueue_event(
        session,
        topic="plant.identification-results.v1",
        event=build_identification_event(
            observation_id=observation.id,
            plant_id=plant.id,
            candidates=[
                EventCandidate(
                    scientific_name=candidate.scientific_name,
                    common_name=candidate.common_name,
                    confidence=candidate.confidence,
                )
                for candidate in candidates[:3]
            ],
            needs_review=not outcome.recognized,
            model_version=outcome.model_version,
        ),
    )
    session.commit()
    return IdentificationResult(
        observation_id=observation.id,
        candidates=candidates,
        recognized=outcome.recognized,
        needs_review=not outcome.recognized,
        model_version=outcome.model_version,
    )


@router.post(
    "/{plant_id}/observations/{observation_id}/analyze-visual",
    response_model=VisualAnalysisResult,
)
def analyze_observation_photo(
    plant_id: UUID,
    observation_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
    analyzer: Annotated[
        VisualConditionAnalyzer, Depends(get_visual_condition_analyzer)
    ],
    current_user: Annotated[User, Depends(get_current_user)],
) -> VisualAnalysisResult:
    observation = require_observation(session, plant_id, observation_id, current_user.id)
    if not observation.photos:
        raise HTTPException(status_code=409, detail="У наблюдения нет фотографии")
    photo = storage.locate(observation.photos[0].storage_key)
    outcome = analyzer.analyze(
        ImageReference(uri=str(photo.path), media_type=photo.media_type)
    )
    return VisualAnalysisResult(
        observation_id=observation.id,
        analyzable=outcome.analyzable,
        findings=[
            VisualFindingResult(code=finding.code, confidence=finding.confidence)
            for finding in outcome.findings
        ],
        model_version=outcome.model_version,
    )


@router.post(
    "/{plant_id}/observations/{observation_id}/analyze-text",
    response_model=TextAnalysisResult,
)
def analyze_observation_description(
    plant_id: UUID,
    observation_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    extractor: Annotated[SymptomExtractor, Depends(get_symptom_extractor)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TextAnalysisResult:
    observation = require_observation(session, plant_id, observation_id, current_user.id)
    outcome = extractor.extract(observation.description or "")
    return TextAnalysisResult(
        observation_id=observation.id,
        analyzable=outcome.analyzable,
        findings=[
            TextFindingResult(code=finding.code, confidence=finding.confidence)
            for finding in outcome.findings
        ],
        model_version=outcome.model_version,
    )


@router.post(
    "/{plant_id}/observations/{current_observation_id}/compare/{reference_observation_id}",
    response_model=PhotoComparisonResult,
)
def compare_observation_photos(
    plant_id: UUID,
    current_observation_id: UUID,
    reference_observation_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
    comparator: Annotated[PhotoComparator, Depends(get_photo_comparator)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PhotoComparisonResult:
    current = require_observation(
        session, plant_id, current_observation_id, current_user.id
    )
    reference = require_observation(
        session, plant_id, reference_observation_id, current_user.id
    )
    if not current.photos or not reference.photos:
        raise HTTPException(status_code=409, detail="Для сравнения нужны две фотографии")
    current_photo = storage.locate(current.photos[0].storage_key)
    reference_photo = storage.locate(reference.photos[0].storage_key)
    outcome = comparator.compare(
        ImageReference(uri=str(reference_photo.path), media_type=reference_photo.media_type),
        ImageReference(uri=str(current_photo.path), media_type=current_photo.media_type),
    )
    return PhotoComparisonResult(
        reference_observation_id=reference.id,
        current_observation_id=current.id,
        comparable=outcome.comparable,
        reasons=list(outcome.reasons),
        metrics=outcome.metrics,
        model_version=outcome.model_version,
    )


@router.post(
    "/{plant_id}/observations/{current_observation_id}/dynamics/{reference_observation_id}",
    response_model=ObservationDynamicsResult,
)
def calculate_observation_dynamics(
    plant_id: UUID,
    current_observation_id: UUID,
    reference_observation_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
    comparator: Annotated[PhotoComparator, Depends(get_photo_comparator)],
    analyzer: Annotated[
        VisualConditionAnalyzer, Depends(get_visual_condition_analyzer)
    ],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ObservationDynamicsResult:
    current = require_observation(
        session, plant_id, current_observation_id, current_user.id
    )
    reference = require_observation(
        session, plant_id, reference_observation_id, current_user.id
    )
    if current.observed_at <= reference.observed_at:
        raise HTTPException(
            status_code=422,
            detail="Текущее наблюдение должно быть сделано позже предыдущего",
        )
    if not current.photos or not reference.photos:
        raise HTTPException(status_code=409, detail="Для сравнения нужны две фотографии")

    current_photo = storage.locate(current.photos[0].storage_key)
    reference_photo = storage.locate(reference.photos[0].storage_key)
    current_reference = ImageReference(
        uri=str(current_photo.path), media_type=current_photo.media_type
    )
    previous_reference = ImageReference(
        uri=str(reference_photo.path), media_type=reference_photo.media_type
    )
    comparison = comparator.compare(previous_reference, current_reference)
    care_events = session.scalars(
        select(CareEvent)
        .where(
            CareEvent.plant_id == plant_id,
            CareEvent.performed_at > reference.observed_at,
            CareEvent.performed_at <= current.observed_at,
        )
        .order_by(CareEvent.performed_at)
    ).all()
    if comparison.comparable:
        previous_analysis = analyzer.analyze(previous_reference)
        current_analysis = analyzer.analyze(current_reference)
        if previous_analysis.analyzable and current_analysis.analyzable:
            dynamics = calculate_dynamics(
                previous_analysis.findings, current_analysis.findings
            )
        else:
            dynamics = calculate_dynamics((), ())
    else:
        dynamics = calculate_dynamics((), ())

    return ObservationDynamicsResult(
        reference_observation_id=reference.id,
        current_observation_id=current.id,
        comparable=comparison.comparable,
        comparison_reasons=list(comparison.reasons),
        trend=(
            dynamics.trend.value
            if comparison.comparable
            else OverallTrend.UNDETERMINED.value
        ),
        changes=[
            FindingChangeResult(
                code=change.code,
                previous_confidence=change.previous_confidence,
                current_confidence=change.current_confidence,
                direction=change.direction.value,
            )
            for change in dynamics.changes
        ],
        care_events=[CareEventResult.model_validate(event) for event in care_events],
    )


@router.post(
    "/{plant_id}/observations/{observation_id}/assess",
    response_model=DecisionAssessmentResult,
    status_code=status.HTTP_201_CREATED,
)
def assess_observation(
    plant_id: UUID,
    observation_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
    identifier: Annotated[PlantIdentifier, Depends(get_plant_identifier)],
    visual_analyzer: Annotated[
        VisualConditionAnalyzer, Depends(get_visual_condition_analyzer)
    ],
    symptom_extractor: Annotated[SymptomExtractor, Depends(get_symptom_extractor)],
    comparator: Annotated[PhotoComparator, Depends(get_photo_comparator)],
    explanation_generator: Annotated[
        GroundedExplanationGenerator, Depends(get_explanation_generator)
    ],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DecisionAssessmentResult:
    plant = require_plant(session, plant_id, current_user.id)
    observation = require_observation(session, plant_id, observation_id, current_user.id)
    if not observation.photos:
        raise HTTPException(status_code=409, detail="У наблюдения нет фотографии")

    photo = storage.locate(observation.photos[0].storage_key)
    image_reference = ImageReference(uri=str(photo.path), media_type=photo.media_type)
    identification = identifier.identify(image_reference)
    visual = visual_analyzer.analyze(image_reference)
    text_analysis = symptom_extractor.extract(observation.description or "")

    previous = session.scalar(
        select(Observation)
        .where(
            Observation.plant_id == plant_id,
            Observation.id != observation.id,
            Observation.observed_at < observation.observed_at,
        )
        .options(selectinload(Observation.photos))
        .order_by(Observation.observed_at.desc())
        .limit(1)
    )
    photos_comparable = None
    dynamics_trend = None
    if previous is not None and previous.photos:
        previous_photo = storage.locate(previous.photos[0].storage_key)
        previous_reference = ImageReference(
            uri=str(previous_photo.path), media_type=previous_photo.media_type
        )
        comparison = comparator.compare(previous_reference, image_reference)
        photos_comparable = comparison.comparable
        if comparison.comparable:
            previous_visual = visual_analyzer.analyze(previous_reference)
            if previous_visual.analyzable and visual.analyzable:
                dynamics_trend = calculate_dynamics(
                    previous_visual.findings, visual.findings
                ).trend.value

    environment_alerts = []
    humidity = float(observation.humidity_pct) if observation.humidity_pct is not None else None
    temperature = (
        float(observation.temperature_c) if observation.temperature_c is not None else None
    )
    if humidity is not None and humidity < 20:
        environment_alerts.append("humidity_too_low")
    elif humidity is not None and humidity > 85:
        environment_alerts.append("humidity_too_high")
    if temperature is not None and temperature < 10:
        environment_alerts.append("temperature_too_low")
    elif temperature is not None and temperature > 35:
        environment_alerts.append("temperature_too_high")

    decision = evaluate(
        AssessmentSignals(
            identification=identification.candidates,
            visual_findings=visual.findings,
            text_findings=text_analysis.findings,
            species_confirmed=plant.species_status == "confirmed",
            image_analyzable=visual.analyzable,
            text_analyzable=text_analysis.analyzable,
            humidity_pct=humidity,
            temperature_c=temperature,
            photos_comparable=photos_comparable,
            dynamics_trend=dynamics_trend,
            environment_alerts=environment_alerts,
        )
    )
    risk_level = {
        RiskLevel.UNDETERMINED: "unknown",
        RiskLevel.LOW: "low",
        RiskLevel.MODERATE: "medium",
        RiskLevel.HIGH: "high",
    }[decision.risk]
    assessment_status = (
        "needs_review"
        if decision.requires_more_data or decision.requires_species_confirmation
        else "succeeded"
    )
    explanation = explanation_generator.explain(
        ExplanationContext(
            risk_level=risk_level,
            evidence_codes=tuple(item.code for item in decision.evidence),
            recommended_actions=decision.recommended_actions,
            missing_inputs=decision.missing_inputs,
            conflicting_evidence=decision.conflicting_evidence,
        )
    )
    top_candidate = identification.candidates[0] if identification.candidates else None
    top_finding = max(decision.evidence, key=lambda item: item.confidence, default=None)
    model_version = "+".join(
        (
            identification.model_version,
            visual.model_version,
            text_analysis.model_version,
            f"policy-{decision.policy_version}",
        )
    )
    identified_scientific_name = (
        candidate_names(top_candidate)[0] if top_candidate is not None else None
    )
    record = AssessmentRecord(
        observation_id=observation.id,
        status=assessment_status,
        identified_scientific_name=identified_scientific_name,
        identification_confidence=(
            Decimal(str(top_candidate.confidence)) if top_candidate is not None else None
        ),
        finding_code=top_finding.code if top_finding is not None else None,
        finding_confidence=(
            Decimal(str(top_finding.confidence)) if top_finding is not None else None
        ),
        risk_level=risk_level,
        explanation=explanation.text,
        model_version=model_version,
    )
    session.add(record)
    session.flush()
    enqueue_event(
        session,
        topic="plant.assessment-results.v1",
        event=build_assessment_event(
            assessment_id=record.id,
            observation_id=observation.id,
            plant_id=plant.id,
            status=assessment_status,
            risk_level=risk_level,
            finding_code=record.finding_code,
            finding_confidence=(
                float(record.finding_confidence)
                if record.finding_confidence is not None
                else None
            ),
            explanation=explanation.text,
            model_version=model_version,
        ),
    )
    session.commit()

    return DecisionAssessmentResult(
        assessment_id=record.id,
        observation_id=observation.id,
        status=assessment_status,
        risk_level=risk_level,
        requires_species_confirmation=decision.requires_species_confirmation,
        requires_more_data=decision.requires_more_data,
        conflicting_evidence=decision.conflicting_evidence,
        missing_inputs=list(decision.missing_inputs),
        evidence=[
            DecisionEvidenceResult(
                code=item.code,
                confidence=item.confidence,
                source=item.source,
            )
            for item in decision.evidence
        ],
        recommended_actions=list(decision.recommended_actions),
        explanation=explanation.text,
        explanation_source=explanation.source,
        policy_version=decision.policy_version,
        model_version=model_version,
    )


@router.post(
    "/{plant_id}/care-events",
    response_model=CareEventResult,
    status_code=status.HTTP_201_CREATED,
)
def create_care_event(
    plant_id: UUID,
    payload: CareEventCreate,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CareEvent:
    require_plant(session, plant_id, current_user.id)
    values = payload.model_dump(exclude_none=True)
    event = CareEvent(plant_id=plant_id, **values)
    session.add(event)
    session.flush()
    enqueue_event(
        session,
        topic="plant.care-events.v1",
        event=build_care_event(
            care_event_id=event.id,
            plant_id=event.plant_id,
            action_type=event.action_type,
            notes=event.notes,
            performed_at=event.performed_at,
        ),
    )
    session.commit()
    session.refresh(event)
    return event


@router.get("/{plant_id}/history", response_model=PlantHistoryResult)
def get_plant_history(
    request: Request,
    plant_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    signer: Annotated[PhotoLinkSigner, Depends(get_photo_link_signer)],
    configuration: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PlantHistoryResult:
    plant = session.scalar(
        select(Plant)
        .where(Plant.id == plant_id, Plant.owner_id == current_user.id)
        .options(
            selectinload(Plant.observations).selectinload(Observation.photos),
            selectinload(Plant.observations).selectinload(Observation.assessments),
            selectinload(Plant.care_events),
        )
    )
    if plant is None:
        raise HTTPException(status_code=404, detail="Растение не найдено")
    observations = sorted(plant.observations, key=lambda item: item.observed_at, reverse=True)
    care_events = sorted(plant.care_events, key=lambda item: item.performed_at, reverse=True)
    assessments = sorted(
        (
            assessment
            for observation in plant.observations
            for assessment in observation.assessments
        ),
        key=lambda item: item.created_at,
        reverse=True,
    )
    return PlantHistoryResult(
        plant=PlantResult.model_validate(plant),
        observations=[
            observation_result(request, observation, signer, configuration)
            for observation in observations
        ],
        care_events=[CareEventResult.model_validate(event) for event in care_events],
        assessments=[StoredAssessmentResult.model_validate(item) for item in assessments],
    )
