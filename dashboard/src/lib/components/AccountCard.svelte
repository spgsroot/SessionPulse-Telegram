<script lang="ts">
  import type { AccountState } from '$lib/api/client';
  import StateIndicator from './StateIndicator.svelte';
  import { maskPhone } from '$lib/utils/formatters';
  import { timeAgo, formatRate } from '$lib/utils/formatters';

  let { account, showPhone = false }: { account: AccountState; showPhone?: boolean } = $props();

  const phone = $derived(showPhone ? account.phone : maskPhone(account.phone));
  const msgRate = $derived(formatRate(account.metrics.messages_1m * 60));
  const lastSeen = $derived(timeAgo(account.last_event_at));
</script>

<a href="/accounts/{encodeURIComponent(account.phone)}" class="card">
  <div class="card-header">
    <span class="phone">{phone}</span>
    <StateIndicator state={account.state} size="sm" />
  </div>
  <div class="card-metrics">
    <div class="metric">
      <span class="metric-value">{msgRate}</span>
      <span class="metric-label">msg/min</span>
    </div>
    <div class="metric">
      <span class="metric-value">{account.metrics.active_channels}</span>
      <span class="metric-label">channels</span>
    </div>
    <div class="metric">
      <span class="metric-value">{lastSeen}</span>
      <span class="metric-label">last event</span>
    </div>
  </div>
  {#if account.error_message}
    <div class="card-error">{account.error_message}</div>
  {/if}
</a>

<style>
  .card {
    display: block;
    background: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 10px;
    padding: 14px 16px;
    text-decoration: none;
    color: inherit;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .card:hover {
    border-color: #585b70;
    box-shadow: 0 0 12px rgba(88, 91, 112, 0.2);
  }
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
  }
  .phone {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.95em;
    color: #cdd6f4;
  }
  .card-metrics {
    display: flex;
    gap: 16px;
  }
  .metric {
    display: flex;
    flex-direction: column;
  }
  .metric-value {
    font-size: 1.05em;
    font-weight: 600;
    color: #cdd6f4;
  }
  .metric-label {
    font-size: 0.7em;
    color: #6c7086;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .card-error {
    margin-top: 8px;
    font-size: 0.78em;
    color: #f38ba8;
    background: rgba(243, 139, 168, 0.08);
    padding: 4px 8px;
    border-radius: 4px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
