export const STATE_COLORS: Record<string, string> = {
  created: '#6b7280',
  connecting: '#3b82f6',
  connected: '#3b82f6',
  monitoring: '#22c55e',
  throttled: '#eab308',
  recovering: '#f97316',
  stopped: '#6b7280',
  error: '#ef4444',
  banned: '#7c2d12',
  deleted: '#1f2937'
};

export const STATE_ICONS: Record<string, string> = {
  monitoring: '\u{1F7E2}',
  throttled: '\u{1F7E1}',
  recovering: '\u{1F7E0}',
  error: '\u{1F534}',
  banned: '\u26D4',
  stopped: '\u26AB',
  connected: '\u{1F535}',
  connecting: '\u{1F535}',
  created: '\u26AA',
  deleted: '\u2B1B'
};

export const SEVERITY_COLORS: Record<string, string> = {
  info: '#3b82f6',
  warning: '#eab308',
  error: '#ef4444',
  critical: '#dc2626'
};

export function stateColor(state: string): string {
  return STATE_COLORS[state] || '#6b7280';
}

export function stateIcon(state: string): string {
  return STATE_ICONS[state] || '\u2753';
}
