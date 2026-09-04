export interface OfficerProfile {
  id: string
  name: string
  role: string
}

export interface AccessibilityPreferences {
  textSize: 'comfortable' | 'large'
  increasedContrast: boolean
  reducedMotion: boolean
}

export const activeOfficer: OfficerProfile = {
  id: import.meta.env.VITE_OFFICER_ID || 'officer:io_114',
  name: import.meta.env.VITE_OFFICER_NAME || 'IO 114',
  role: import.meta.env.VITE_OFFICER_ROLE || 'Investigation Officer',
}

const OFFICER_STORAGE_KEY = 'caselens.officer-profile'
const ACCESSIBILITY_STORAGE_KEY = 'caselens.accessibility'

export const defaultAccessibilityPreferences: AccessibilityPreferences = {
  textSize: 'comfortable',
  increasedContrast: false,
  reducedMotion: false,
}

export function loadOfficerProfile(): OfficerProfile {
  try {
    const saved = window.localStorage.getItem(OFFICER_STORAGE_KEY)
    if (!saved) return activeOfficer
    return { ...activeOfficer, ...(JSON.parse(saved) as Partial<OfficerProfile>) }
  } catch {
    return activeOfficer
  }
}

export function saveOfficerProfile(profile: OfficerProfile) {
  window.localStorage.setItem(OFFICER_STORAGE_KEY, JSON.stringify(profile))
}

export function loadAccessibilityPreferences(): AccessibilityPreferences {
  try {
    const saved = window.localStorage.getItem(ACCESSIBILITY_STORAGE_KEY)
    if (!saved) return defaultAccessibilityPreferences
    return {
      ...defaultAccessibilityPreferences,
      ...(JSON.parse(saved) as Partial<AccessibilityPreferences>),
    }
  } catch {
    return defaultAccessibilityPreferences
  }
}

export function saveAccessibilityPreferences(preferences: AccessibilityPreferences) {
  window.localStorage.setItem(ACCESSIBILITY_STORAGE_KEY, JSON.stringify(preferences))
}
