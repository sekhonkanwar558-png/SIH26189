import * as Tooltip from '@radix-ui/react-tooltip'
import { BriefcaseBusiness, ChevronLeft, ChevronRight } from 'lucide-react'
import type { AccessibilityPreferences, OfficerProfile } from '../config'
import { BrandMark } from './BrandMark'
import { SettingsDrawer } from './SettingsDrawer'

export interface SidebarNavItem {
  key: string
  label: string
  icon: React.ReactNode
  active?: boolean
  onSelect?: () => void
}

interface SidebarProps {
  collapsed: boolean
  mobileOpen: boolean
  officer: OfficerProfile
  preferences: AccessibilityPreferences
  onCollapseChange: (collapsed: boolean) => void
  onMobileClose: () => void
  onSettingsSave: (
    officer: OfficerProfile,
    preferences: AccessibilityPreferences,
  ) => void
  /** Defaults to the case list. Inside a case this is the case's own sections. */
  items?: SidebarNavItem[]
  /** Sits above the nav — a Back to Cases link when inside a case. */
  aboveNav?: React.ReactNode
}

export function Sidebar({
  collapsed,
  mobileOpen,
  officer,
  preferences,
  onCollapseChange,
  onMobileClose,
  onSettingsSave,
  items,
  aboveNav,
}: SidebarProps) {
  const nameParts = officer.name.trim().split(/\s+/)
  const firstLetters = nameParts[0]?.replace(/[^a-z]/gi, '') ?? ''
  const initials =
    nameParts.length === 1 || !/[a-z]/i.test(nameParts[1] ?? '')
      ? firstLetters.slice(0, 2).toUpperCase()
      : nameParts
          .slice(0, 2)
          .map((part) => part.charAt(0))
          .join('')
          .toUpperCase()

  return (
    <Tooltip.Provider delayDuration={500}>
      {mobileOpen && (
        <button
          type="button"
          aria-label="Close navigation menu"
          onClick={onMobileClose}
          className="fixed inset-0 z-40 hidden bg-[#20252B]/20 max-[899px]:block"
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex flex-col border-r border-line bg-panel transition-[width,transform] duration-200 max-[899px]:w-[240px] max-[899px]:shadow-[12px_0_36px_rgba(32,37,43,0.10)] ${mobileOpen ? 'max-[899px]:translate-x-0' : 'max-[899px]:-translate-x-full'} ${collapsed ? 'w-[72px]' : 'w-[240px]'}`}
      >
        <div className={`flex h-[76px] items-center border-b border-line ${collapsed ? 'justify-center' : 'px-5'}`}>
          <div className="flex items-center gap-2.5">
            <BrandMark size={34} />
            {!collapsed && (
              <div>
                <div className="text-[17px] font-semibold tracking-[-0.02em] text-ink">CaseLens</div>
                <div className="mt-0.5 text-[11px] font-medium tracking-[0.03em] text-muted">
                  See every connection.
                </div>
              </div>
            )}
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-5" aria-label="Main navigation">
          {aboveNav && !collapsed && <div className="mb-3">{aboveNav}</div>}
          {items ? (
            <div className="space-y-1">
              {items.map((item) => (
                <SidebarItem
                  key={item.key}
                  collapsed={collapsed}
                  label={item.label}
                  active={item.active}
                  onSelect={item.onSelect}
                >
                  {item.icon}
                </SidebarItem>
              ))}
            </div>
          ) : (
            <SidebarItem collapsed={collapsed} label="Cases" active>
              <BriefcaseBusiness size={19} strokeWidth={1.8} />
            </SidebarItem>
          )}
        </nav>

        <div className="border-t border-line p-3">
          <SettingsDrawer
            collapsed={collapsed}
            officer={officer}
            preferences={preferences}
            onSave={onSettingsSave}
          />
          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <button
                type="button"
                className={`mt-1 flex h-10 w-full items-center rounded-lg text-sm font-medium text-muted transition-colors hover:bg-canvas hover:text-ink max-[899px]:hidden ${collapsed ? 'justify-center' : 'gap-3 px-3'}`}
                onClick={() => onCollapseChange(!collapsed)}
                aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              >
                {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
                {!collapsed && <span>Collapse sidebar</span>}
              </button>
            </Tooltip.Trigger>
            {collapsed && (
              <Tooltip.Portal>
                <Tooltip.Content
                  side="right"
                  sideOffset={8}
                  className="z-50 rounded-md bg-ink px-2.5 py-1.5 text-xs text-white"
                >
                  Expand sidebar
                </Tooltip.Content>
              </Tooltip.Portal>
            )}
          </Tooltip.Root>

          <div className={`mt-3 flex items-center border-t border-line pt-4 ${collapsed ? 'justify-center' : 'gap-3 px-2'}`}>
            <div className="grid size-9 shrink-0 place-items-center rounded-full border border-line-strong bg-canvas text-xs font-semibold text-ink">
              {initials || 'IO'}
            </div>
            {!collapsed && (
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-ink">{officer.name}</p>
                <p className="mt-0.5 truncate text-xs text-muted">{officer.role}</p>
              </div>
            )}
          </div>
        </div>
      </aside>
    </Tooltip.Provider>
  )
}

interface SidebarItemProps {
  collapsed: boolean
  label: string
  active?: boolean
  onSelect?: () => void
  children: React.ReactNode
}

function SidebarItem({ collapsed, label, active = false, onSelect, children }: SidebarItemProps) {
  const item = (
    <button
      type="button"
      onClick={onSelect}
      className={`flex h-11 w-full items-center rounded-lg text-sm font-semibold transition-colors ${collapsed ? 'justify-center' : 'gap-3 px-3'} ${active ? 'bg-civic-soft text-civic' : 'text-muted hover:bg-canvas hover:text-ink'}`}
      aria-current={active ? 'page' : undefined}
      aria-label={label}
    >
      {children}
      {!collapsed && <span>{label}</span>}
    </button>
  )

  if (!collapsed) return item

  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>{item}</Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side="right"
          sideOffset={8}
          className="z-50 rounded-md bg-ink px-2.5 py-1.5 text-xs text-white"
        >
          {label}
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  )
}
