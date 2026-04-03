import { writable, derived } from 'svelte/store';
import type { AccountState } from '$lib/api/client';

export const accounts = writable<AccountState[]>([]);
export const accountsLoading = writable(false);

export const summary = derived(accounts, ($accounts) => {
  const byState: Record<string, number> = {};
  for (const a of $accounts) {
    byState[a.state] = (byState[a.state] || 0) + 1;
  }
  return { total: $accounts.length, by_state: byState };
});

export const monitoringAccounts = derived(accounts, ($a) =>
  $a.filter((a) => a.state === 'monitoring')
);

export const errorAccounts = derived(accounts, ($a) =>
  $a.filter((a) => ['error', 'banned', 'recovering'].includes(a.state))
);

export function updateAccountState(phone: string, newState: string, extra?: Record<string, unknown>): void {
  accounts.update(($accounts) =>
    $accounts.map((a) =>
      a.phone === phone
        ? { ...a, state: newState, ...extra }
        : a
    )
  );
}
