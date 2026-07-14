# Routes

Route optimization for trash collection in Chihuahua, Chihuahua. The initial scope covers Oxxo store pickups; other customers will be added later.

See [CLAUDE.md](CLAUDE.md) for the development workflow followed in this repo.

## Problem statement

# Problem: Multi-Trip Capacitated Vehicle Routing with Intermediate Disposal

## Objective
Minimize total route time across all trucks. Landfill trips are already costed in via travel time (distance matrix) plus disposal time, so minimizing time naturally minimizes trips; no separate penalty term needed.

## Fleet
- Number of trucks: 10 (estimate — treat as fixed for now, will confirm exact number)
- Truck capacity: 8 cbm per truck (estimate — treat as fixed for now, will confirm exact number)
- Depot location: 28.692373626788008, -106.1213508365314
- Do trucks return to depot at end of shift? Yes

## Disposal
- Landfill location(s): 28.69977986701721, -106.03304097168068
- Time cost per disposal event (queue + dump; travel time to/from the landfill is captured separately in the distance matrix): 15 minutes

## Stops
- Total number of stops: 220
- Per-stop trash quantity (demand): assume uniform, 0.9 cbm per stop
- Service time per stop (time spent collecting, not traveling): 3 minutes, uniform across all stops
- Time windows, if any: none for now

## Scope
- Single shift, single day, each stop visited exactly once, no repeat/periodic visits.

## Distances / Travel Times
- Source: Google Maps Distance Matrix API
- Note: 222 points (220 stops + depot + landfill) means roughly 49,000 pairwise distances. Google's API caps requests at 25x25 origins/destinations, so the matrix needs to be built in batches (roughly 80 requests), not a single call.

## Constraints
- A truck must return to a landfill before its load exceeds capacity, and may resume collecting stops afterward.
- Every stop must be visited exactly once, by exactly one truck.
- [ADD ANY OTHERS: driver shift length caps, no-left-turn restrictions, one-way streets, etc.]

## Deliverable requested from Claude
- Assignment of stops to trucks
- Ordered route per truck, including all landfill visits
- Total time and distance per truck, and in aggregate
- Number of landfill trips per truck

## Notes for the solver
- At 0.9 cbm per stop and 8 cbm capacity, each truck reaches capacity after 8 stops (8 x 0.9 = 7.2 cbm; a 9th stop would exceed capacity at 8.1 cbm). With 22 stops per truck on average, expect roughly 2 landfill trips per truck as a baseline, not an edge case.
- At this scale (220 stops, 10 trucks), an exact optimal solution is likely computationally impractical. Expect a heuristic or metaheuristic result (e.g., via OR-Tools or similar), not a certified global optimum.
