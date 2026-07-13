# ADR-027: Cat Trap Temporal-Median Mask Baseline

**Status:** Rejected for production; retained as a diagnostic baseline

## Context

The Cat Trap dash fixture uses a mostly static painted background, but also contains generated speed lines, dust, glow, and character motion. The prior alpha and chroma-key baselines could not evaluate this footage.

## Decision

Add `opencv.temporal-median.v1` as a deterministic sequence baseline. It fits a median background from 30 evenly sampled frames, thresholds Lab color distance, suppresses thin horizontal structures, and retains the largest nearby connected foreground regions.

The 240-frame fixture is evaluated with centroid-aligned temporal metrics and a worst-pair contact sheet. Generated masks remain local and ignored; the aggregate JSON report and diagnostic contact sheet are versioned.

## Result

- Mean centroid-aligned IoU: 0.8380
- Minimum centroid-aligned IoU: 0.3956
- Mean boundary turnover: 0.8059
- Maximum boundary turnover: 0.9904
- Mean foreground ratio: 0.2459

Visual inspection shows merged speed lines and dust, missing interior character regions, and unstable boundaries around hair, cape, weapons, and effects. The baseline is therefore rejected for production extraction.

## Consequences

The benchmark now proves that deterministic static-background subtraction is insufficient for the real fixture. The next candidate must use object-aware or video-aware segmentation, while preserving the same benchmark contract and manual ground-truth requirement.
