# Design Decisions

This project is small by design. The current knowledge base describes one
reviewed public profile, and that narrow domain is what makes the behavior
auditable. The goal is not to make a model sound confident across open-ended
topics. The goal is to answer when verified context is present, and to refuse
cleanly when it is not.

## Reviewed Knowledge Is The Boundary

The reviewed knowledge file is the source of truth. Visitor questions,
retrieval scores, model output, and operator review notes do not become facts by
themselves.

That rule keeps the system understandable. If an answer appears, it should be
possible to trace it back to a reviewed source and a visible source locator. If
a question cannot be supported from that material, the correct behavior is a
refusal or a clarification request.

## Retrieval Proposes, Policy Decides

Retrieval is allowed to be broad. It can combine vector search, keyword search,
and intent-expanded search to gather plausible context. It can also use semantic
candidate intents to widen the candidate pool.

It still does not decide whether the answer is allowed. The answerability policy
does that separately, using the retrieved context, configured score threshold,
matched required intents, accepted categories, and required evidence terms. This
split is the central safety boundary of the project: a strong-looking but
irrelevant chunk should not become an answer just because it ranked well.

## The Model Has A Narrow Job

The language model phrases approved context. It does not own truth, select
sources, classify support, or decide whether a question is answerable.

This is especially important for a CPU-oriented architecture. Smaller local
models are useful when the application gives them a bounded task. The routing
catalog, retrieval fan-out, rank fusion, policy gate, deterministic fallbacks,
and source handling reduce the amount of judgment delegated to the model.

## Intent Routing Is Reviewed Configuration

The intent catalog is runtime configuration, not portfolio knowledge. It defines
the question patterns the system supports, the knowledge categories those
questions may use, the evidence terms required by policy, and the lexical terms
retrieval may use for expansion.

Semantic examples are reviewed anchors for matching. Their vectors live in
memory at runtime, and semantic matches remain retrieval candidates unless a
reviewed, model-bound calibration threshold promotes them to required intent
status. Calibration proposes thresholds; it does not write the committed catalog.

## Refusal Is A Product Behavior

The assistant is expected to refuse salary guesses, private contact details,
personal residence, favorite-food questions, internal diagnostics, and other
unsupported requests. A refusal means the policy could not prove the answer from
reviewed context. It is not an exception path and it is not left to the model to
improvise.

The same principle applies to availability or open-to-work claims. Suitability
questions can be answered from reviewed skills evidence, but actual availability
requires its own reviewed public fact.

## Question Collection Does Not Learn

When enabled, unanswered-question collection stores only raw question text after
the final status is `not_answerable`. It stores no visitor identity, browser
metadata, language, answer text, answer status, sources, source IDs, or retrieval
scores.

Those questions help the operator notice gaps and decide whether the reviewed
knowledge or catalog should change. They never update the knowledge base or
intent catalog automatically.

## Configuration Fails Fast

Runtime settings are explicit. Missing catalog paths, malformed intent data,
model/calibration mismatches, missing retrieval fan-out, and invalid provider
settings fail startup instead of silently falling back to hidden defaults.

That makes deployment less forgiving in the short term, but easier to reason
about over time. If the assistant is running, it is running with the catalog,
knowledge, provider, and retrieval settings the operator selected.
