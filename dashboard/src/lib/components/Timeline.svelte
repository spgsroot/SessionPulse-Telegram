<script lang="ts">
  import type { TimelineEvent } from '$lib/api/client';
  import { SEVERITY_COLORS } from '$lib/utils/colors';

  let { events }: { events: TimelineEvent[] } = $props();

  function eventIcon(type: string): string {
    if (type === 'state_change') return '\u{1F504}';
    if (type === 'metric') return '\u{1F4CA}';
    if (type === 'event') return '\u{1F4E8}';
    if (type === 'span') return '\u23F1';
    return '\u2022';
  }

  function formatTime(iso: string): string {
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return iso;
    }
  }
</script>

<div class="timeline">
  {#each events as event}
    <div class="entry" style="border-left-color: {SEVERITY_COLORS[event.severity] || '#3b82f6'}">
      <div class="entry-header">
        <span class="time">{formatTime(event.timestamp)}</span>
        <span class="icon">{eventIcon(event.event_type)}</span>
        <span class="type">{event.event_name || event.event_type}</span>
        <span class="severity" style="color: {SEVERITY_COLORS[event.severity] || '#6c7086'}">{event.severity}</span>
      </div>
      {#if event.message}
        <div class="message">{event.message}</div>
      {/if}
    </div>
  {/each}
  {#if events.length === 0}
    <div class="empty">No events yet</div>
  {/if}
</div>

<style>
  .timeline {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .entry {
    padding: 8px 12px;
    background: #1e1e2e;
    border-left: 3px solid;
    border-radius: 0 6px 6px 0;
  }
  .entry-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.85em;
  }
  .time {
    font-family: 'JetBrains Mono', monospace;
    color: #6c7086;
    font-size: 0.9em;
    min-width: 70px;
  }
  .icon { font-size: 1em; }
  .type {
    color: #cdd6f4;
    font-weight: 500;
    flex: 1;
  }
  .severity {
    font-size: 0.75em;
    text-transform: uppercase;
    font-weight: 600;
  }
  .message {
    margin-top: 4px;
    font-size: 0.8em;
    color: #a6adc8;
    padding-left: 78px;
  }
  .empty {
    text-align: center;
    color: #6c7086;
    padding: 24px;
    font-size: 0.9em;
  }
</style>
