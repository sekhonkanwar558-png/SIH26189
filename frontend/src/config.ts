/**
 * Who is using this. One officer, no login — SIH is a prototype and an auth
 * flow is a screen between a judge and the product.
 */
export interface OfficerProfile {
  id: string
  name: string
}

export const activeOfficer: OfficerProfile = {
  id: import.meta.env.VITE_OFFICER_ID || 'officer:io_114',
  name: import.meta.env.VITE_OFFICER_NAME || 'IO 114',
}
