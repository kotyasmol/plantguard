import { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function Icon({ children, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

export function LeafMark(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M19 3.5C11.8 4.2 6.2 7.2 5 13.1c-.7 3.4 1.7 6.4 5.2 6.4 6.3 0 8.7-7.7 8.8-16Z" />
      <path d="M4 21c2.8-5 6.4-8.7 11-11.4" />
      <path d="M11.5 13.2c.2-2.1 0-3.8-.7-5.2" />
    </Icon>
  );
}

export function HomeIcon(props: IconProps) {
  return <Icon {...props}><path d="m3 10 9-7 9 7" /><path d="M5 9v11h14V9" /><path d="M9 20v-6h6v6" /></Icon>;
}

export function PlantIcon(props: IconProps) {
  return <Icon {...props}><path d="M12 21v-9" /><path d="M12 14c-5 0-7-2.8-7-7 4.5 0 7 2.2 7 7Z" /><path d="M12 11c0-4.8 2.7-7 7-7 0 4.2-2 7-7 7Z" /><path d="M7 21h10" /></Icon>;
}

export function CameraIcon(props: IconProps) {
  return <Icon {...props}><path d="M4 7h3l1.4-2h7.2L17 7h3v12H4Z" /><circle cx="12" cy="13" r="4" /></Icon>;
}

export function HistoryIcon(props: IconProps) {
  return <Icon {...props}><path d="M4 5v5h5" /><path d="M5.5 17.5A8 8 0 1 0 4.2 9" /><path d="M12 8v5l3 2" /></Icon>;
}

export function PlusIcon(props: IconProps) {
  return <Icon {...props}><path d="M12 5v14M5 12h14" /></Icon>;
}

export function DropletIcon(props: IconProps) {
  return <Icon {...props}><path d="M12 3S6.5 9.2 6.5 14a5.5 5.5 0 0 0 11 0C17.5 9.2 12 3 12 3Z" /></Icon>;
}

export function ThermometerIcon(props: IconProps) {
  return <Icon {...props}><path d="M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0Z" /><path d="M12 17V8" /></Icon>;
}

export function WarningIcon(props: IconProps) {
  return <Icon {...props}><path d="m12 3 10 18H2Z" /><path d="M12 9v5M12 18h.01" /></Icon>;
}

export function ChevronIcon(props: IconProps) {
  return <Icon {...props}><path d="m9 6 6 6-6 6" /></Icon>;
}

export function CareIcon(props: IconProps) {
  return <Icon {...props}><path d="M7 20h10" /><path d="M9 20c-2-4-1-7 3-9 4 2 5 5 3 9" /><path d="M12 11c-4 0-6-2-6-5 3.8 0 6 1.7 6 5Z" /><path d="M12 9c0-3.4 2-5 5-5 0 3-1.6 5-5 5Z" /></Icon>;
}

export function LogoutIcon(props: IconProps) {
  return <Icon {...props}><path d="M10 4H4v16h6" /><path d="M14 8l4 4-4 4M18 12H9" /></Icon>;
}
