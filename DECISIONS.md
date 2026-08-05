# Decisions Log

### 1. Handling the 60% Missing Topology
**Decision**: Generate a Spatial Minimum Spanning Tree (MST) on backend startup for any DT lacking `seq_on_line` and `parent_pole_id`.
**Alternatives rejected**:
- *Falling back to coarse DT-level localization*: Rejected because an MST, while imperfect, provides highly probable span-level resolution (since physical lines often follow the shortest path between nearby poles). Providing a "Medium Confidence" span is better than dropping all resolution to a generic DT-level error.
- *Learning topology over time from outages*: Rejected due to scope (monsoon peaks provide data, but waiting for faults to map the network defeats the purpose of day-one resolution).
**Assumption**: Poles assigned to a specific `dt_id` represent a localized geographic cluster and do not wildly overlap with poles from neighboring DTs.

### 2. Debouncing and Out-of-Order Packets
**Decision**: Wait 3 minutes (180s) after the first `power_lost` event before running the localization traversal.
**Alternatives rejected**:
- *Instant evaluation*: With $\pm$90s clock skew and varying network delivery times, running instant evaluation would spawn dozens of fragmented tickets as upstream and downstream nodes drop offline asynchronously. 
**Assumption**: The control room's target metric is "under two minutes" vs "two hours today". A 3-minute debounce slightly extends this but vastly increases accuracy. (We can tune this down to 90s if strictly necessary).

### 3. Noise Filtering (Dead Sensors)
**Decision**: If a pole reports DARK, but has LIVE children downstream, it is treated as a sensor anomaly and ignored during ticket creation.
**Alternatives rejected**:
- *Creating a "low priority" ticket*: Fails the "don't cry wolf" constraint. The control room only cares about real outages, not bad modems.

### 4. Selecting the AI Feature
**Decision**: Built an endpoint to parse unstructured field notes into structured JSON.
**Alternatives rejected**:
- *LLM doing fault localization*: Explicitly forbidden and mathematically unsound. Graph traversals are fast and deterministic.
- *LLM writing incident summaries*: Marginal value. A UI can present structured spans and affected counts perfectly well without an LLM converting them to paragraphs.

### What I would do with two more weeks
1. **Topology Refinement**: I would cross-reference the Spatial MST with OpenStreetMap road data to prevent edges from crossing buildings or unnavigable terrain.
2. **Persistent Debouncing**: Move the debounce timers out of simple Redis TTLs into a proper durable task queue (like Celery or RabbitMQ) to survive backend restarts.
3. **Advanced AI**: Use the AI to compare the expected geographic span to historical crew repair logs, learning over time if an inferred MST edge repeatedly points crews to the wrong street.
