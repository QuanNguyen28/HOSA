# HOSA decision-support context

Status: current. This guide explains the purpose and interpretation of existing capabilities. It is not a source of new measurements, mission outcomes or a replacement for the current schemas and engine evidence.

## The decision the user is making

At the lunar south pole the Sun and Earth can lie close to the local horizon. Local terrain can obstruct them, and changing the observation point or mission dates changes the geometry. HOSA helps someone compare specified points and time windows to understand whether the requested geometric illumination and Earth visibility are available and which requirement or uncertainty drives the outcome. It supports the challenge's goal of accessible visual exploration and rapid comparison. A useful explanation connects those geometric conditions to the user's planning question, rather than treating a metric table as the answer.

The map locates the observer, the terrain and sky view help explain horizon clearance, and the timeline reveals when visibility changes. Point analysis addresses one target/window. Compare evaluates requested alternatives on the same stated basis. Best-date search evaluates allowed candidate start times within the user's search range under the chosen requirements and ranking. A best sampled candidate is not proof of the global optimum or permission to move outside the requested scope.

## Interpreting trade-offs

Total availability and continuity answer different questions. Total Earth visibility measures how much geometric opportunity exists in the mission window. A longest interruption describes how fragmented that opportunity may be. If a user needs a sustained contact session, the contact-window requirements must be evaluated; total visible time alone does not establish that a usable session exists. Setup time and first-contact deadline can change which windows are usable. Geometric visibility still does not establish antenna gain, throughput, ground-station availability or a successful radio link.

Sunlight is the time integral of visible solar-disc area for the default model, not generated electricity. A high average does not establish continuous exposure or survival through a dark interval. Explain the relevance to solar exposure or an interruption concern without assigning a battery capacity, endurance or thermal safety. Equipment heights affect the terrain-horizon geometry only when evaluated by the backend; do not promise that raising an antenna fixes an uncomputed case.

Hard requirements determine the engine's decision. Optional darkness/blackout preferences describe desirable behavior and may help discuss trade-offs, but violating a soft preference is not itself a hard failure. Explain a comparison in relation to the user's priorities and the engine's actual ranking. Different criteria may favor different candidates; do not invent a universal quality score.

## What an unresolved result means

INDETERMINATE means the engine cannot support a final conclusion with the evidence and validation available. A nominal result that looks favorable does not erase a validation gate or missing coverage. An unfavorable definitive hard requirement can remain FAIL even with other warnings. Some requests can pass conservative mission-path bounds without full-circle validation; report the actual validation scope instead of claiming full scientific certification. Explain the specific recorded cause, not a generic warning or an invented obstructing crater.

## Data and display play different roles

NASA LOLA/PGDA elevation products support terrain geometry. SPICE shared ephemerides and JPL Horizons comparisons support Sun/Earth directions where the actual observer/time coverage and validation permit. A region in the catalog is an inventory entry, not proof of an installed DEM or evaluated mission. Archived P1 responses cannot be transferred to a different observer. Missing source assets remain missing.

NASA Moon Trek imagery adds photographic surface context. WAC provides broad coverage; the registered NAC south-pole mosaic provides finer imagery where its extent covers the view. It is drawn over the existing terrain and does not replace DEM heights, improve a computed horizon, or create new validated coverage. Imagery records lighting at acquisition; the sunlight simulation instead follows the selected mission time. Inspect the registered source metadata for native versus served tile resolution, and never infer scientific precision from how sharp a scene looks.

## Conversation and explanation

A conceptual or hypothetical question can be answered without a mission date. A request for a concrete result needs the backend's required target, window and requirements. Resolve pronouns and short follow-ups from conversation, keep explicit user corrections, and ask only for missing information needed for that action. General chat prepares and explains; mission planning reviews concrete parameters before evaluation. Applied plans change only through explicit confirmation.

The model writes its own answer from relevant source passages and result evidence. These paragraphs describe relationships and limits, not canned responses. Present the conclusion first, explain the relevant cause in familiar language, and use numerical detail only when it resolves the user's question. Follow the user's language, including when the conversation switches languages. Admit when the available sources cannot support the requested conclusion.
