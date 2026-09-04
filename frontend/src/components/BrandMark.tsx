interface BrandMarkProps {
  size?: number
}

export function BrandMark({ size = 36 }: BrandMarkProps) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 40 40"
      width={size}
      height={size}
      fill="none"
    >
      <circle cx="18" cy="18" r="11.5" stroke="#245B8A" strokeWidth="2.5" />
      <path d="M26.3 26.3 34 34" stroke="#245B8A" strokeWidth="3" strokeLinecap="round" />
      <path d="m12.5 20.5 5-5 6 3" stroke="#245B8A" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="12.5" cy="20.5" r="2.2" fill="#FFFFFF" stroke="#245B8A" strokeWidth="1.5" />
      <circle cx="17.5" cy="15.5" r="2.2" fill="#FFFFFF" stroke="#245B8A" strokeWidth="1.5" />
      <circle cx="23.5" cy="18.5" r="2.7" fill="#C58B2A" stroke="#FFFFFF" strokeWidth="1.2" />
    </svg>
  )
}
