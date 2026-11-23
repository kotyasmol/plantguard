#!/usr/bin/env python3
"""Populate an existing PlantGuard account with a varied demo collection."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from plantguard_api.config import Settings
from plantguard_api.database import Assessment, CareEvent, Observation, Plant, User
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

COLLECTION = (
    {
        "nickname": "толстянка",
        "scientific_name": "Crassula ovata",
        "common_name": "Толстянка яйцевидная",
        "observations": (
            (
                -14,
                "Листья слегка сморщились, грунт полностью просох.",
                43,
                24,
                "leaf-wilting",
                0.66,
                "medium",
                (
                    "Растению не хватает влаги: листья немного потеряли упругость. "
                    "Полейте умеренно после полного просыхания грунта."
                ),
            ),
            (
                0,
                "После полива листья снова плотные, точка роста активна.",
                48,
                23,
                "healthy-growth",
                0.91,
                "low",
                (
                    "Толстянка выглядит здоровой: листья упругие, признаков гнили "
                    "или вредителей не видно."
                ),
            ),
        ),
        "care": (-7, "watered", "Умеренный полив после полного просыхания грунта"),
    },
    {
        "nickname": "Мона",
        "scientific_name": "Monstera deliciosa",
        "common_name": "Монстера деликатесная",
        "observations": (
            (
                -12,
                "Разворачивается новый лист, окраска равномерная.",
                61,
                23,
                "healthy-growth",
                0.88,
                "low",
                "Монстера развивается нормально: новый лист раскрывается без пятен и деформаций.",
            ),
            (
                -2,
                "Новый лист полностью раскрылся, повреждений и пятен нет.",
                64,
                23,
                "healthy-growth",
                0.95,
                "low",
                (
                    "Растение в хорошем состоянии. Поддерживайте рассеянный свет "
                    "и текущий режим полива."
                ),
            ),
        ),
        "care": (-8, "fertilized", "Половинная доза удобрения для декоративно-лиственных"),
    },
    {
        "nickname": "Потос",
        "scientific_name": "Epipremnum aureum",
        "common_name": "Эпипремнум золотистый",
        "observations": (
            (
                -10,
                "Нижние листья стали заметно светлее.",
                74,
                22,
                "leaf-yellowing",
                0.72,
                "medium",
                (
                    "Пожелтение нижних листьев может быть связано с переувлажнением "
                    "или недостатком света."
                ),
            ),
            (
                0,
                "Два нижних листа пожелтели, грунт остаётся мокрым четвёртый день.",
                82,
                21,
                "leaf-yellowing",
                0.89,
                "medium",
                (
                    "Вероятно переувлажнение. Дайте грунту просохнуть, проверьте "
                    "дренаж и временно отмените полив."
                ),
            ),
        ),
        "care": (-4, "moved", "Переставлен ближе к окну с рассеянным светом"),
    },
    {
        "nickname": "Каучук",
        "scientific_name": "Ficus elastica",
        "common_name": "Фикус каучуконосный",
        "observations": (
            (
                -8,
                "На нижней стороне листа появились светлые точки.",
                46,
                24,
                "pest-damage",
                0.71,
                "medium",
                (
                    "Светлые точки похожи на ранние следы вредителей. "
                    "Осмотрите нижнюю сторону листьев."
                ),
            ),
            (
                0,
                "На молодых листьях тонкая паутинка и множество светлых проколов.",
                38,
                25,
                "pest-damage",
                0.94,
                "high",
                (
                    "Высокая вероятность паутинного клеща. Изолируйте растение, "
                    "промойте листья и проведите обработку."
                ),
            ),
        ),
        "care": (0, "treated", "Изолирован и обработан от паутинного клеща"),
    },
    {
        "nickname": "Калли",
        "scientific_name": "Goeppertia zebrina",
        "common_name": "Калатея зебрина",
        "observations": (
            (
                -9,
                "Листья вечером сильнее скручиваются, чем обычно.",
                34,
                25,
                "leaf-curling",
                0.68,
                "medium",
                (
                    "Скручивание листьев связано с сухим воздухом. Калатее требуется "
                    "более высокая влажность."
                ),
            ),
            (
                0,
                "Края трёх листьев стали сухими и коричневыми.",
                29,
                26,
                "leaf-dry-edges",
                0.91,
                "high",
                (
                    "Воздух слишком сухой для калатеи. Повышайте влажность постепенно "
                    "и исключите холодный сквозняк."
                ),
            ),
        ),
        "care": (-3, "moved", "Убрана от батареи и поставлена рядом с увлажнителем"),
    },
    {
        "nickname": "Драко",
        "scientific_name": "Dracaena fragrans",
        "common_name": "Драцена душистая",
        "observations": (
            (
                -15,
                "После пересадки листья сохраняют упругость.",
                51,
                22,
                "healthy-growth",
                0.86,
                "low",
                "Драцена хорошо перенесла пересадку, признаков стресса не обнаружено.",
            ),
            (
                -3,
                "Появился новый лист, окраска ровная, кончики не сохнут.",
                53,
                22,
                "healthy-growth",
                0.94,
                "low",
                "Драцена здорова и продолжает рост. Сохраняйте текущие условия.",
            ),
        ),
        "care": (-16, "repotted", "Пересадка в рыхлый субстрат с дренажным слоем"),
    },
    {
        "nickname": "Окси",
        "scientific_name": "Oxalis triangularis",
        "common_name": "Кислица треугольная",
        "observations": (
            (
                -7,
                "Появилось несколько новых цветоносов.",
                57,
                21,
                "healthy-growth",
                0.90,
                "low",
                "Кислица активно растёт и готовится к цветению.",
            ),
            (
                -1,
                "Растение цветёт, листья раскрываются утром и закрываются вечером.",
                59,
                22,
                "healthy-growth",
                0.97,
                "low",
                "Кислица выглядит здоровой: суточное движение листьев естественно для этого вида.",
            ),
        ),
        "care": (-5, "watered", "Небольшой полив после подсыхания верхнего слоя"),
    },
    {
        "nickname": "Беня",
        "scientific_name": "Ficus benjamina",
        "common_name": "Фикус Бенджамина",
        "observations": (
            (
                -11,
                "После перестановки опало несколько листьев.",
                45,
                20,
                "leaf-drop",
                0.69,
                "medium",
                (
                    "Фикус реагирует на смену места. Не переставляйте его повторно "
                    "и наблюдайте за динамикой."
                ),
            ),
            (
                0,
                "Листья массово опадают, на части листьев появились тёмные пятна.",
                79,
                18,
                "leaf-drop",
                0.93,
                "high",
                (
                    "Сочетание переувлажнения, прохлады и стресса вызывает сильный "
                    "листопад. Проверьте корни и сократите полив."
                ),
            ),
        ),
        "care": (-12, "moved", "Переставлен из комнаты ближе к окну"),
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True, help="Existing account email")
    parser.add_argument("--database-url", default=Settings().database_url)
    return parser.parse_args()


def seed(email: str, database_url: str) -> tuple[int, int, int, int]:
    engine = create_engine(database_url)
    now = datetime.now(timezone.utc)
    created_plants = created_observations = created_assessments = created_care = 0
    with Session(engine) as session:
        user = session.scalar(select(User).where(User.email == email.lower()))
        if user is None:
            raise SystemExit(f"Account not found: {email}")

        for index, item in enumerate(COLLECTION):
            plant = session.scalar(
                select(Plant).where(
                    Plant.owner_id == user.id,
                    Plant.nickname == item["nickname"],
                )
            )
            if plant is None:
                plant = Plant(
                    owner_id=user.id,
                    nickname=item["nickname"],
                    created_at=now - timedelta(days=90 - index * 4),
                )
                session.add(plant)
                session.flush()
                created_plants += 1
            plant.species_scientific_name = item["scientific_name"]
            plant.species_common_name = item["common_name"]
            plant.species_status = "confirmed"
            plant.updated_at = now

            previous_assessment = None
            for observation_data in item["observations"]:
                (
                    day_offset,
                    description,
                    humidity,
                    temperature,
                    finding_code,
                    confidence,
                    risk_level,
                    explanation,
                ) = observation_data
                observed_at = now + timedelta(days=day_offset, minutes=-index)
                observation = session.scalar(
                    select(Observation).where(
                        Observation.plant_id == plant.id,
                        Observation.description == description,
                    )
                )
                if observation is None:
                    observation = Observation(
                        plant_id=plant.id,
                        description=description,
                        humidity_pct=Decimal(humidity),
                        temperature_c=Decimal(temperature),
                        observed_at=observed_at,
                        created_at=observed_at,
                    )
                    session.add(observation)
                    session.flush()
                    created_observations += 1
                else:
                    observation.humidity_pct = Decimal(humidity)
                    observation.temperature_c = Decimal(temperature)
                    observation.observed_at = observed_at
                    observation.created_at = observed_at
                assessment = session.scalar(
                    select(Assessment).where(Assessment.observation_id == observation.id)
                )
                if assessment is None:
                    assessment = Assessment(
                        observation_id=observation.id,
                        previous_assessment_id=(
                            previous_assessment.id if previous_assessment else None
                        ),
                        status="succeeded",
                        identified_scientific_name=item["scientific_name"],
                        identification_confidence=Decimal("0.94"),
                        finding_code=finding_code,
                        finding_confidence=Decimal(str(confidence)),
                        risk_level=risk_level,
                        explanation=explanation,
                        model_version="demo-curated-1.0",
                        created_at=observed_at + timedelta(minutes=1),
                    )
                    session.add(assessment)
                    session.flush()
                    created_assessments += 1
                else:
                    assessment.previous_assessment_id = (
                        previous_assessment.id if previous_assessment else None
                    )
                    assessment.status = "succeeded"
                    assessment.identified_scientific_name = item["scientific_name"]
                    assessment.identification_confidence = Decimal("0.94")
                    assessment.finding_code = finding_code
                    assessment.finding_confidence = Decimal(str(confidence))
                    assessment.risk_level = risk_level
                    assessment.explanation = explanation
                    assessment.model_version = "demo-curated-1.0"
                    assessment.created_at = observed_at + timedelta(minutes=1)
                previous_assessment = assessment

            care_day, action_type, notes = item["care"]
            care_event = session.scalar(
                select(CareEvent).where(
                    CareEvent.plant_id == plant.id,
                    CareEvent.notes == notes,
                )
            )
            if care_event is None:
                performed_at = now + timedelta(days=care_day, minutes=-index)
                session.add(
                    CareEvent(
                        plant_id=plant.id,
                        action_type=action_type,
                        notes=notes,
                        performed_at=performed_at,
                        created_at=performed_at,
                    )
                )
                created_care += 1
            else:
                care_event.action_type = action_type
                care_event.performed_at = now + timedelta(days=care_day, minutes=-index)
                care_event.created_at = care_event.performed_at

        session.commit()
    engine.dispose()
    return created_plants, created_observations, created_assessments, created_care


def main() -> None:
    args = parse_args()
    counts = seed(args.email, args.database_url)
    print(
        "Demo collection is ready: "
        f"{counts[0]} plants, {counts[1]} observations, "
        f"{counts[2]} assessments, {counts[3]} care events created."
    )


if __name__ == "__main__":
    main()
