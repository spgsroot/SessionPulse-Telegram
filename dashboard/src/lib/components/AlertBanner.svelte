<script lang="ts">
  import { firingAlerts } from '$lib/stores/alerts';
  import { SEVERITY_COLORS } from '$lib/utils/colors';
  import { timeAgo } from '$lib/utils/formatters';
</script>

{#if $firingAlerts.length > 0}
  <div class="banner">
    {#each $firingAlerts.slice(0, 3) as alert}
      <div class="alert-item" style="border-left-color: {SEVERITY_COLORS[alert.severity] || '#eab308'}">
        <span class="severity">{alert.severity}</span>
        <span class="message">{alert.message}</span>
        <span class="time">{timeAgo(alert.fired_at)}</span>
      </div>
    {/each}
    {#if $firingAlerts.length > 3}
      <a href="/alerts" class="more">+{$firingAlerts.length - 3} more alerts</a>
    {/if}
  </div>
{/if}

<style>
  .banner {
    background: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 8px;
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 16px;
  }
  .alert-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 10px;
    background: rgba(243, 139, 168, 0.05);
    border-left: 3px solid;
    border-radius: 4px;
    font-size: 0.85em;
  }
  .severity {
    text-transform: uppercase;
    font-weight: 700;
    font-size: 0.7em;
    letter-spacing: 0.05em;
    min-width: 60px;
    color: #f9e2af;
  }
  .message {
    flex: 1;
    color: #cdd6f4;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .time {
    color: #6c7086;
    font-size: 0.85em;
    flex-shrink: 0;
  }
  .more {
    text-align: center;
    color: #89b4fa;
    font-size: 0.8em;
    text-decoration: none;
    padding: 4px;
  }
  .more:hover { text-decoration: underline; }
</style>
