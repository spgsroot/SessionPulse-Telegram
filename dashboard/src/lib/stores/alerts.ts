import { writable, derived } from 'svelte/store';
import type { Alert } from '$lib/api/client';

export const alerts = writable<Alert[]>([]);

export const firingAlerts = derived(alerts, ($a) =>
  $a.filter((a) => a.status === 'firing')
);

export const firingCount = derived(firingAlerts, ($f) => $f.length);
