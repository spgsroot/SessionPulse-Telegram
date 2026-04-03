<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import type { PipelineHealth } from '$lib/api/client';
  import PipelineFlow from '$lib/components/PipelineFlow.svelte';

  let pipeline: PipelineHealth | null = $state(null);
  let loading = $state(true);

  onMount(async () => {
    await refresh();
    loading = false;

    const interval = setInterval(refresh, 10000);
    return () => clearInterval(interval);
  });

  async function refresh() {
    try {
      pipeline = await api.pipeline.health();
    } catch (e) {
      console.error('Pipeline fetch failed:', e);
    }
  }

  const stages = ['capture', 'produce', 'consume', 'store', 'ml_score'];
  const stageLabels: Record<string, string> = {
    capture: 'Event Capture (Telethon)',
    produce: 'Kafka Producer (Redpanda)',
    consume: 'Kafka Consumer (Worker)',
    store: 'ClickHouse Insert',
    ml_score: 'ML Scoring (Transformer)'
  };
</script>

<svelte:head>
  <title>Pipeline - SessionPulse</title>
</svelte:head>

<div class="section">
  <div class="section-header">
    <h1>Event Pipeline</h1>
    <button class="btn" onclick={refresh}>Refresh</button>
  </div>
</div>

{#if loading}
  <div class="loading">Loading pipeline data...</div>
{:else if pipeline}
  <div class="section">
    <PipelineFlow {pipeline} />
  </div>

  <div class="section">
    <h2>Stage Details</h2>
    <div class="stage-list">
      {#each stages as stage}
        {@const s = pipeline.stages[stage]}
        {#if s}
          <div class="stage-detail card">
            <div class="stage-header">
              <h3>{stageLabels[stage] || stage}</h3>
              <span class="stage-status" class:healthy={s.status === 'healthy'} class:degraded={s.status === 'degraded'}>
                {s.status}
              </span>
            </div>
            <div class="stage-metrics">
              <div class="metric">
                <span class="metric-value">{s.throughput.toFixed(1)}</span>
                <span class="metric-label">events/sec</span>
              </div>
              <div class="metric">
                <span class="metric-value">{s.latency_p50.toFixed(0)}ms</span>
                <span class="metric-label">p50 latency</span>
              </div>
              <div class="metric">
                <span class="metric-value">{s.latency_p95.toFixed(0)}ms</span>
                <span class="metric-label">p95 latency</span>
              </div>
            </div>
          </div>
        {/if}
      {/each}
    </div>
  </div>
{/if}

<style>
  .loading {
    text-align: center;
    color: var(--text-muted);
    padding: 48px;
  }
  .stage-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 12px;
  }
  .stage-detail {
    padding: 14px 16px;
  }
  .stage-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
  }
  .stage-header h3 {
    font-size: 0.92em;
    color: var(--text-primary);
  }
  .stage-status {
    font-size: 0.75em;
    font-weight: 600;
    text-transform: uppercase;
    padding: 2px 8px;
    border-radius: 10px;
  }
  .stage-status.healthy {
    background: rgba(34, 197, 94, 0.12);
    color: #22c55e;
  }
  .stage-status.degraded {
    background: rgba(234, 179, 8, 0.12);
    color: #eab308;
  }
  .stage-metrics {
    display: flex;
    gap: 24px;
  }
  .metric {
    display: flex;
    flex-direction: column;
  }
  .metric-value {
    font-size: 1.1em;
    font-weight: 600;
    color: var(--text-primary);
  }
  .metric-label {
    font-size: 0.72em;
    color: var(--text-muted);
    text-transform: uppercase;
  }
</style>
