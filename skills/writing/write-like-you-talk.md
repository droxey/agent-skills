---
id: "write-like-you-talk"
name: "Write Like You Talk"
description: "Rewrite stiff, artificial, or AI-sounding prose into writing that feels natural, direct, and human while preserving meaning, precision, and audience fit."
version: "0.1.0"
tags: ["writing", "editing", "style", "voice", "communication"]
verification: "Verify the rewrite preserves factual meaning, scope, certainty, and required technical or legal force while improving natural cadence and readability."
---

# Write Like You Talk

## Purpose

Transform stiff, artificial, overly formal, or AI-sounding prose into writing that feels natural, direct, and human while preserving meaning, precision, and audience fit.

This skill does **not** transcribe raw speech. It rewrites prose to carry the clarity, rhythm, and directness of strong spoken explanation, with the structure and compression of good writing.

## Use This Skill When

Use this skill when the user asks to:

- make writing sound more natural
- humanize text
- remove AI tone
- make prose sound like them
- make writing clearer or less stiff
- rewrite formal prose into conversational prose
- improve cadence, flow, or readability
- preserve meaning while improving voice

## Do Not Use This Skill When

Do not use this skill when the user asks for:

- legal language that must remain formal
- contractual or policy language where tone softening may change force
- heavily structured academic citation formatting only
- verbatim transcription of speech
- dialect imitation, accent imitation, or identity mimicry
- vague “make it better” requests where the real need is shortening, outlining, fact-checking, or tone-shifting without a conversational goal

If another task is primary, do that task first or pair this skill only as a final polish pass.

## Core Principle

Write with the clarity and natural rhythm of speech, but with the structure, precision, and editing discipline of writing.

## Outcomes

The rewritten text should:

- sound like a smart person explaining something clearly
- keep the original meaning and commitments intact
- reduce stiffness, pomp, and empty formality
- improve rhythm, sentence movement, and readability
- stay appropriate for the audience and domain

## Non-Goals

This skill must **not**:

- add filler, rambling, or false intimacy
- flatten strong ideas into generic plainness
- remove necessary technical language
- change claims, promises, timelines, or facts
- invent personality traits or biography details
- make expert writing unserious

## Inputs

Expected inputs, when available:

- source text
- audience
- context
- desired tone
- degree of informality
- length target
- whether jargon should be preserved, reduced, or translated
- whether the user wants explanation, rewrite only, or teaching notes

If some inputs are missing, infer conservatively from the text and task.

## Default Operating Mode

Default to a two-step flow:

1. Diagnose briefly
2. Rewrite

Keep the diagnosis short unless the user explicitly asks for a detailed explanation.

## Rewrite Modes

### 1. Light Edit

Use when the draft is mostly solid but sounds slightly stiff.

Do:
- tighten wording
- smooth awkward phrasing
- reduce obvious AI or corporate tone
- preserve structure

### 2. Strong Rewrite

Use when the draft is bloated, unnatural, overly formal, or obviously synthetic.

Do:
- rebuild sentences for natural flow
- reduce abstraction
- replace weak constructions with direct ones
- re-sequence ideas if needed for clarity

### 3. Teach the Pattern

Use when the user wants to learn.

Do:
- provide the rewrite
- identify a few repeatable changes
- explain what made the original feel unnatural

### 4. Voice-Calibrated Rewrite

Use when the user has a defined voice.

Do:
- preserve the user’s known style
- match audience and medium
- use the minimum amount of voice necessary

## Detection Heuristics

Look for these signals of stiff or artificial prose:

### Inflated phrasing

Examples:
- “in order to” instead of “to”
- “facilitate” instead of “help”
- “utilize” instead of “use”
- “with respect to” instead of “about”

### Abstract noun piles

Examples:
- “implementation of optimization strategies”
- “development of alignment processes”
- “improvement of communication effectiveness”

Prefer strong verbs over noun-heavy constructions.

### Empty transitions and scaffolding

Examples:
- “It is important to note that”
- “In today’s rapidly evolving landscape”
- “Needless to say”
- “At the end of the day”

Delete unless they do real work.

### Repetitive cadence

Examples:
- multiple sentences starting the same way
- same sentence length repeated too long
- overly balanced, synthetic rhythm

Vary sentence shape deliberately.

### Hedge stacking

Examples:
- “might potentially help to”
- “somewhat arguably suggests”
- “it seems as though perhaps”

Keep only the uncertainty that is actually warranted.

### False polish

Examples:
- generic inspirational phrasing
- consultant tone
- academic throat-clearing
- overly symmetrical sentence pairs

Prefer specificity and motion.

## Rewrite Rules

### Meaning preservation

Do not change:
- factual claims
- scope
- level of certainty
- commitments
- deadlines
- numbers
- names
- legal or technical force

### Precision preservation

Keep jargon when it is the shortest accurate term for the audience.

Replace jargon only when:
- it is unnecessary
- it hides weak thinking
- the audience is unlikely to understand it
- a simpler term is equally precise

### Cadence improvement

Prefer:
- concrete subjects
- active verbs
- shorter dependency chains
- earlier arrival of the main point
- sentence length variation
- paragraph flow that sounds speakable when read aloud

### Structure improvement

Where needed:
- move the main point earlier
- split overloaded sentences
- merge choppy fragments
- reorder ideas for comprehension
- cut repetition

### Tone control

Aim for:
- direct
- clear
- grounded
- human
- audience-appropriate

Avoid:
- chatty filler
- fake warmth
- slang unless clearly requested
- identity performance
- exaggerated certainty

## Output Format

Default output:

### Revised Version

Provide the rewritten text first.

### What Changed

Then list 3 to 6 concrete changes only if useful:
- cut inflated phrasing
- replaced abstract nouns with verbs
- tightened sentence movement
- preserved technical terms
- reduced hedging
- reordered ideas for clarity

If the user asks for rewrite only, return rewrite only.

## Quality Bar

A successful rewrite passes all of these checks:

- The meaning is unchanged.
- The prose sounds natural when read aloud.
- The main point arrives earlier.
- The sentences are easier to follow.
- The text is less performative.
- Necessary technical precision remains.
- The result sounds human without becoming sloppy.

## Read-Aloud Test

Before finalizing, silently test:

- Would a real person say something close to this?
- Does any sentence sound memorized, corporate, or machine-balanced?
- Does the sentence carry too many abstract nouns before the verb arrives?
- Is any phrase present only to sound polished?

If yes, revise again.

## Escalation Rules

If the source text is highly sensitive or force-bearing, such as:
- contracts
- policies
- legal notices
- compliance language
- grading criteria
- technical safety instructions

then preserve the formal structure unless the user clearly asks for a parallel plain-English version.

When in doubt, produce:
1. safe original-force version
2. plain-English companion version

## Example Transformations

### Example 1: Corporate stiffness

**Input**  
We are reaching out to provide you with an update regarding the implementation timeline for the new platform migration initiative.

**Output**  
Here’s an update on the timeline for the platform migration.

**Why it works**  
- removes throat-clearing
- swaps noun pile for direct phrasing
- keeps meaning intact

### Example 2: Academic stiffness

**Input**  
This paper seeks to explore the ways in which students demonstrate varying levels of engagement with AI-mediated feedback systems.

**Output**  
This paper looks at how students engage with AI-based feedback systems.

**Why it works**  
- shortens the lead-in
- reduces formal padding
- keeps the research claim

### Example 3: AI-sounding prose

**Input**  
In today’s rapidly evolving technological landscape, organizations must strategically leverage innovative solutions in order to remain competitive.

**Output**  
As technology changes, organizations need to use new tools well if they want to stay competitive.

**Why it works**  
- removes cliché framing
- replaces generic buzzwords
- makes the sentence say one thing clearly

## Failure Modes

This skill has failed if it:

- sounds flatter but not more human
- becomes vague while trying to sound simple
- removes necessary expert language
- shifts tone too casual for the context
- introduces filler or fake personality
- keeps the same ideas but turns them into generic internet prose

## Preferred Decision Order

When tradeoffs appear, prioritize in this order:

1. preserve meaning
2. preserve force and precision
3. improve clarity
4. improve rhythm
5. increase naturalness
6. add style only if still appropriate

## Instructor Mode

If the user wants to learn the pattern, explain in this order:

1. what felt stiff
2. what changed
3. why the revision sounds more human
4. what rule they can reuse next time

Keep explanations concrete. Use line edits, not theory-heavy abstraction.

## Minimal Response Templates

### Rewrite only
- revised text

### Rewrite plus quick notes
- revised text
- 3 to 5 bullets on what changed

### Teach mode
- original problem patterns
- revised version
- transferable rules

## Acceptance Checklist

Before returning, confirm:

- [ ] Meaning preserved
- [ ] Precision preserved
- [ ] Stronger verbs used where possible
- [ ] Abstract padding reduced
- [ ] Read-aloud flow improved
- [ ] Audience fit maintained
- [ ] No fake warmth or filler added

## Invocation Hint

When a user says “make this sound more like me,” “humanize this,” “make it less AI,” or “write like I talk,” use this skill.
