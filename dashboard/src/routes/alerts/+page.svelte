<script lang="ts">
  import { onMount } from 'svelte';
  import { alerts, firingAlerts } from '$lib/stores/alerts';
  import { api } from '$lib/api/client';
  import { SEVERITY_COLORS } from '$lib/utils/colors';
  import { timeAgo, maskPhone } from '$lib/utils/formatters';

  let loading = $state(true);

  onMount(async () => {
    try {
      const res = await api.alerts.list();
      alerts.set(res.alerts);
    } catch (e) {
      console.error('Alerts fetch failed:', e);
    }
    loading = false;
  });

  async function acknowledge(id: string) {
    try {
      await api.alerts.acknowledge(id);
      alerts.update(($a) =>
        $a.map((a) => a.alert_id === id ? { ...a, status: 'acknowledged' } : a)
      );
    } catch (e) {
      console.error('Acknowledge failed:', e);
    }
  }

  async function refresh() {
    try {
      const res = await api.alerts.list();
      alerts.set(res.alerts);
    } catch { /* ignore */ }
  }
</script>

<svelte:head>
  <title>Alerts - SessionPulse</title>
</svelte:head>

<div class="section">
  <div class="section-header">
    <h1>Alerts ({$alerts.length})</h1>
    <div style="display:flex;gap:8px">
      <a href="/alerts/rules" class="btn">Manage Rules</a>
      <button class="btn" onclick={refresh}>Refresh</button>
    </div>
  </div>
</div>

{#if loading}
  <div class="loading">Loading alerts...</div>
{:else if $alerts.length === 0}
  <div class="empty">
    <div class="empty-icon">&#x2705;</div>
    <div class="empty-text">No alerts. All systems operational.</div>
  </div>
{:else}
  <div class="alerts-list">
    {#each $alerts as alert (alert.alert_id)}
      <div
        class="alert-card"
        class:firing={alert.status === 'firing'}
        class:resolved={alert.status === 'resolved'}
        class:acknowledged={alert.status === 'acknowledged'}
        style="border-left-color: {SEVERITY_COLORS[alert.severity] || '#eab308'}"
      >
        <div class="alert-header">
          <span class="alert-severity badge" class:badge-red={alert.severity === 'critical'} class:badge-yellow={alert.severity === 'warning'}>
            {alert.severity}
          </span>
          <span class="alert-rule">{alert.rule_name}</span>
          <span class="alert-status badge" class:badge-red={alert.status === 'firing'} class:badge-green={alert.status === 'resolved'} class:badge-gray={alert.status === 'acknowledged'}>
            {alert.status}
          </span>
        </div>
        <div class="alert-message">{alert.message}</div>
        <div class="alert-footer">
          <span class="alert-entity">{alert.entity_type}: {maskPhone(alert.entity_id)}</span>
          <span class="alert-time">Fired {timeAgo(alert.fired_at)}</span>
          {#if alert.status === 'firing'}
            <button class="btn ack-btn" onclick={() => acknowledge(alert.alert_id)}>
              Acknowledge
            </button>
          {/if}
        </div>
      </div>
    {/each}
  </div>
{/if}

<style>
  .loading, .empty {
    text-align: center;
    color: var(--text-muted);
    padding: 48px;
  }
  .empty-icon { font-size: 2.5em; margin-bottom: 12px; }
  .empty-text { font-size: 1.1em; }
  .alerts-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .alert-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-left: 4px solid;
    border-radius: 8px;
    padding: 14px 16px;
  }
  .alert-card.firing {
    background: rgba(239, 68, 68, 0.04);
  }
  .alert-card.resolved {
    opacity: 0.6;
  }
  .alert-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }
  .alert-rule {
    font-weight: 600;
    font-size: 0.9em;
    flex: 1;
    color: var(--text-primary);
  }
  .alert-message {
    font-size: 0.88em;
    color: var(--text-secondary);
    margin-bottom: 8px;
  }
  .alert-footer {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 0.8em;
  }
  .alert-entity {
    color: var(--text-muted);
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.9em;
  }
  .alert-time {
    color: var(--text-muted);
    flex: 1;
  }
  .ack-btn {
    font-size: 0.85em;
    padding: 4px 10px;
    border-color: var(--yellow);
    color: var(--yellow);
  }
  .ack-btn:hover {
    background: rgba(234, 179, 8, 0.1);
  }
</style>
