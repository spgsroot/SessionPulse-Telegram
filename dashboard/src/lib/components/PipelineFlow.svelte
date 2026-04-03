<script lang="ts">
  import type { PipelineHealth } from '$lib/api/client';
  import { stateColor } from '$lib/utils/colors';

  let { pipeline }: { pipeline: PipelineHealth } = $props();

  const stages = ['capture', 'produce', 'consume', 'store', 'ml_score'];
  const stageLabels: Record<string, string> = {
    capture: 'Capture',
    produce: 'Kafka',
    consume: 'Consumer',
    store: 'ClickHouse',
    ml_score: 'ML Score'
  };

  function statusColor(status: string): string {
    if (status === 'healthy') return '#22c55e';
    if (status === 'degraded') return '#eab308';
    if (status === 'down') return '#ef4444';
    return '#6b7280';
  }
</script>

<div class="pipeline">
  <div class="pipeline-header">
    <h3>Event Pipeline</h3>
    <span class="status" style="color: {statusColor(pipeline.status)}">{pipeline.status}</span>
  </div>
  <div class="stages">
    {#each stages as stage, i}
      {@const s = pipeline.stages[stage]}
      {#if s}
        <div class="stage">
          <div class="stage-dot" style="background: {statusColor(s.status)}"></div>
          <div class="stage-name">{stageLabels[stage]}</div>
          <div class="stage-metrics">
            <span>{s.throughput.toFixed(0)}/s</span>
            <span class="latency">p95: {s.latency_p95.toFixed(0)}ms</span>
          </div>
        </div>
        {#if i < stages.length - 1}
          <div class="arrow">&rarr;</div>
        {/if}
      {/if}
    {/each}
  </div>
</div>

<style>
  .pipeline {
    background: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 10px;
    padding: 16px;
  }
  .pipeline-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
  }
  .pipeline-header h3 {
    margin: 0;
    font-size: 0.95em;
    color: #cdd6f4;
  }
  .status {
    font-size: 0.8em;
    font-weight: 600;
    text-transform: uppercase;
  }
  .stages {
    display: flex;
    align-items: center;
    gap: 4px;
    overflow-x: auto;
  }
  .stage {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    min-width: 80px;
    padding: 8px;
    background: #181825;
    border-radius: 8px;
  }
  .stage-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }
  .stage-name {
    font-size: 0.75em;
    color: #a6adc8;
    font-weight: 500;
  }
  .stage-metrics {
    display: flex;
    flex-direction: column;
    align-items: center;
    font-size: 0.78em;
    color: #cdd6f4;
  }
  .latency {
    color: #6c7086;
    font-size: 0.9em;
  }
  .arrow {
    color: #45475a;
    font-size: 1.2em;
    flex-shrink: 0;
  }
</style>
