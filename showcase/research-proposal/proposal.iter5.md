# FactGuard: Source-Internal Retrieval vs. External Grounding for an Automatic, Human-Free Faithful-Summarization Loop

## 1. Problem

Large language models (LLMs) are increasingly used to summarize scientific papers, but they
routinely **hallucinate** — stating findings, numbers, or causal claims that the source paper
does not support. In a scientific setting these errors are especially damaging: a fabricated
effect size or an invented citation can propagate into downstream literature reviews and
decisions. We want LLM-generated scientific summaries whose claims are, to a measurable and
verifiable degree, **traceable to the source paper itself** — and we want an automatic,
human-free pipeline that *quantifies* and *reduces* the residual unsupported-claim rate rather
than asserting it away.

We are explicit and balanced about the theoretical ceiling. On the one hand, hallucination
cannot be *fully* eliminated by a system that relies on the LLM to police itself: it is formally
shown that "*It will not eliminate hallucination w.r.t. an exponential-time ground truth
function, no matter how many layers are added or how much additional training data are
provided*" (Xu et al., *Hallucination is Inevitable: An Innate Limitation of Large Language
Models*, S2 ID 267069207). On the other hand, that result holds over an *infinite* input set;
for a *fixed* benchmark the probability can be driven down: "*we prove that hallucinations can be
made statistically negligible, provided that the quality and quantity of the training data are
sufficient ... while hallucinations on an infinite set of inputs cannot be entirely eliminated,
their probability can always be reduced by improving algorithms and training data*" (Kalai et
al., *Hallucinations are inevitable but can be made statistically negligible*, S2 ID 276422285).
We therefore do **not** target a hallucination-free summary, nor an abstract "toward zero" goal.
We target a **quantified relative reduction in unsupported claims down to a practical floor that
we define and measure**. That floor is set by **two empirically measured quantities on our actual
target domain (cs.CL scientific papers), not the theoretical infinite-input bound**: (i) the
**retriever's own evidence-recall ceiling** (Recall@k) on each paper — faithfulness cannot exceed
the fraction of claims whose grounding evidence the retriever can actually surface — and (ii) the
**document-NLI verifier's measured accuracy** on a human-labeled cs.CL supported-vs-hallucinated
set. We tie the headline residual-rate target to BOTH measured quantities jointly (Section 3),
because a claim that the retriever cannot surface cannot be kept, and a claim the verifier
mis-judges can be wrongly kept or wrongly cut. **Both floors are reported as intervals**, not
point estimates: we pre-register the human-labeled subset sizes and report confidence intervals
on verifier precision/recall AND Recall@k (Section 3), because even fine-tuned document-level
entailment models on realistic claim-verification data are "*still substantially lower than human
performance (64.3 vs 83.3 F1 at the claim-level)*" and "*WICE is challenging even for fine-tuned
models*" (Kamoi et al., *WiCE: Real-World Entailment for Claims in Wikipedia*, S2 ID 257280052) —
a gap that large means a small calibration set could yield a noisy floor unless its uncertainty
is reported explicitly. Reporting both floors as intervals in one protocol is the honest target
against which the residual rate is stated.

## 2. Proposed methodology

We propose **FactGuard**, an **automatic, human-free** loop that combines **source-internal
(paper-chunk) dense retrieval** with **cross-family LLM/NLI self-verification** and a
**candidate-gated revision loop**. The core idea — a summarizer drafts, retrieval grounds each
sentence against the source paper's own passages, a verifier flags unsupported sentences, and
the loop iterates until nothing is flagged — is preserved unchanged. What this revision hardens
is (a) the **representation of the summary itself**, so that each unit is one verifiable claim and
localization becomes *reliable* rather than merely *measured*; (b) the verifier so that silence is
not mistaken for faithfulness; (c) the gate so that its own reliability is measured and is no
longer bottlenecked by unreliable localization; and (d) the contribution so that the value of
*source-internal* grounding is **demonstrated by ablation** against a curated external scientific
source, not asserted.

1. **Atomic-fact-per-sentence structured summarizer (NEW — lifts the localization ceiling).** The
   summarizer LLM does **not** emit free-form prose. It produces the draft as a sequence of
   **atomic-fact units — one verifiable claim per sentence (explicit claim spans)** — using the
   FActScore-style decomposition that "*breaks a generation down into a series of atomic facts*"
   (Min et al., *FActScore*, S2 ID 258841470). Each unit is constrained to assert a single
   checkable proposition, so that the mapping from a flagged unit to "the unsupported claim" is
   **structural, not inferred by an auto-localizer**. This is the load-bearing soundness change of
   this revision, and it is grounded directly in the localization evidence: LLMs "*are able to
   self-localize effectively in a manner that improves downstream performance with structured
   reasoning traces, but are less reliable at self-localization when operating on unstructured CoT
   traces*", and on unstructured traces "*Using a tolerance of 10% of the solution length,
   agreement reaches only 58%*", whereas "*Localization quality directly impacts correction
   performance within structure*" (Tan et al., *Structure Enables Effective Self-Localization of
   Errors in LLMs*, S2 ID 285271322). Because localization is reliable **within structured units**
   and unreliable on unstructured text, we **raise the gate's ceiling by structuring the summary**
   rather than by tuning the verifier. This is the well-established **Decompose-Then-Verify**
   regime, which "*has shown effective for pinpointing errors and improving factual precision ...
   decomposing text into sub-claims, retrieving supporting materials from a knowledge source, and
   using a verifier to assess each sub-claim*" (Huang et al., *Decomposition Dilemmas: Does Claim
   Decomposition Boost or Burden Fact-Checking Performance?*, S2 ID 273821007). We adopt the same
   guardrails that line of work flags: superficially fine-grained sub-claims with trivial
   information can inflate verification precision, so we (i) **pin the decomposer** (Section 3,
   reporting the residual rate over two pinned decomposers) and (ii) keep the
   **coverage/informativeness control** (Section 3) so structuring cannot game faithfulness by
   shedding content. Crucially, structuring **converts localization from an inferred span into a
   unit identity**: the verifier flags a *unit*, and the gate edits *that unit*, so the gate no
   longer inherits the verifier's error as auto-localization error. We then **measure the
   residual localization quality directly**: span-level localization accuracy of the structured
   units against human-marked spans, and we report the candidate-gate false-accept/false-reject
   rates **conditioned on localizer-correct vs. localizer-wrong cases**, separating gate failures
   caused by mis-localization from gate failures caused by faithfulness-scoring error (S_loc,
   S_selfloc).
2. **Source-internal retriever.** For each draft **atomic-fact unit** we retrieve evidence from the
   *source paper's own chunks* (not an external corpus). We pair a **high-recall dense
   retriever** with a **higher-precision selector** before handing evidence to the verifier,
   because dense embedding selection "*generalizes better with a high recall, while [a sequence
   labeling approach] has higher precision*" (Bekoulis et al., *Improving Evidence Retrieval
   for Automated Explainable Fact-Checking*, S2 ID 231779510). We **re-rank by verifier
   utility** — ranking candidate passages by how much each changes a verifier's support
   decision — because top-k similarity "*ranking ... do[es] not always align with the judgments
   made by the claim verifier*" and feedback-based retrieval beats relevance-only retrieval
   (Zhang et al., *From Relevance to Utility: Evidence Retrieval with Feedback for Fact
   Verification*, S2 ID 264288748). **To break the retrieval–verification feedback loop** in
   which a verifier's blind spots can bias which evidence is surfaced, the utility re-ranker is
   driven by a **held-out re-ranking verifier that is a distinct model from the accept/reject
   verifier** in step 4. This decoupling is directly validated by +VeriRel, which reports "*the
   benefit of decoupling the training of the verification reward model and the final claim
   verifier*" and that, so decoupled, the re-ranker "*consistently improves retrieval accuracy*"
   (Liu et al., *+VeriRel: Verification Feedback to Enhance Document Retrieval for Scientific
   Fact Checking*, S2 ID 280671618). Because +VeriRel still derives the re-ranker's signal *from*
   verification success, decoupling alone does not guarantee *decorrelated* blind spots: a
   systematically blind verifier family can still bias surfaced evidence. We therefore **do not
   assume** the two verifiers err independently — we **measure** it: we report the **error-correlation
   between the re-ranking verifier and the deciding verifier on the human-labeled cs.CL set**
   (Section 3), maximizing architectural diversity (different pretraining families, not just
   different checkpoints) and reporting error-correlation per error type (numeric vs. causal
   claims), since the failure is verifier-specific, not random. A low error-correlation is the
   actual evidence that the feedback loop is broken; merely using a "distinct model" is not (S3, S2).
3. **Cross-family verifier with a document-level NLI backbone (no same-model dependency).** The
   support / contradicted / not-addressed decision is **not** made by the summarizer's own model.
   We use two independent signals:
   (a) a **document-level / long-premise NLI entailment classifier**, framing faithfulness as
   entailment of each atomic-fact unit by its retrieved source passages. We deliberately do
   **not** use a stock short-premise NLI checkpoint, because "*out-of-the-box entailment models
   do not yet offer the desired performance ... the domain shift from the NLI dataset to the
   summarization dataset ... NLI models tend to rely on heuristics such as lexical overlap ...
   existing NLI models generalize poorly*" (Pagnoni et al., *The Factual Inconsistency Problem
   in Abstractive Text Summarization: A Survey*, S2 ID 233476302). Instead we use a model trained
   on **document-granularity premises**, where "*the premises always stay in the document
   granularity, whereas the hypotheses vary in length from single sentences to passages*" and "*a
   model pretrained on DocNLI ... generalizes well to out-of-domain NLP tasks that rely on
   inference at document granularity*" (Yin et al., *DocNLI: A Large-scale Dataset for
   Document-level Natural Language Inference*, S2 ID 235458620). DocNLI is retained as the
   **backbone**. For source passages exceeding the model's input limit we apply a
   **chunk-and-aggregate "stretching" protocol**, but — correcting iter3 — we **do not aggregate
   with MAX alone**. WiCE's MAX rule ("*we derive a document-level score by taking the maximum
   local score*", Kamoi et al., *WiCE: Real-World Entailment for Claims in Wikipedia*, S2 ID
   257280052) discards the distributional signal across chunks. SummaC shows MAX is the **weaker**
   aggregator: the learned-convolution variant SummaC_Conv beats the max-only SummaC_ZS,
   "*demonstrating ... the importance of considering the entire distribution of document scores
   for each summary sentence, instead of taking only the maximum score*", and SummaC_Conv
   "*achieves the best benchmark performance at 74.4%*" balanced accuracy (Laban et al., *SummaC*,
   S2 ID 244345901). We therefore **adopt SummaC_Conv-style distributional aggregation** over the
   per-chunk DocNLI scores as the default, and **report MAX vs. mean vs. learned-conv side by
   side on the cs.CL set, adopting whichever is empirically best** (Section 3). Because the
   Conv-beats-MAX advantage is established on **news**, not document-granularity scientific
   claims — and because WiCE's own results found "*predicting scores at the chunk-level works
   better than sentence-level using the MAX strategy*" (S2 ID 257280052), i.e. MAX was competitive
   at chunk granularity in that setting — we **calibrate the learned-conv layer (or at minimum its
   threshold) on the cs.CL human-labeled subset rather than reusing SummaC's news-trained conv
   weights**, and report the aggregator comparison **stratified by source-passage length** (short
   vs. long premises), since the MAX-vs-Conv gap should widen only when many chunks contribute.
   We further report a **lexical-overlap control** (Section 3) so that the verifier's accept
   decisions are shown not to be explained by surface n-gram overlap.
   (b) a **verifier LLM from a different model family than the summarizer**, because intrinsic
   self-correction without external feedback fails — "*without external feedback, LLMs struggle to
   properly judge the correctness of their prior responses*" (S2 ID 273403610), so an independent
   cross-family verifier is the right architecture.
   The two signals are combined at a **tunable operating point**, not a fixed AND-gate: we expose
   the NLI score threshold and report the full **NLI-vs-LLM agreement/disagreement breakdown**
   (both-flag, NLI-only, LLM-only, neither) so the recall lost to requiring agreement is visible
   and tunable, rather than hidden behind a single AND decision. This is motivated by SummaC's
   74.4% balanced-accuracy ceiling, which implies the document-NLI signal itself errs ~1-in-4 even
   at SOTA (S2 ID 244345901); we treat that as a **measured reliability bound** rather than a
   guarantee that silence equals faithfulness.
4. **Candidate-gated revision loop over structured units.** The summarizer proposes a
   rewrite/deletion for each flagged **atomic-fact unit**, but the edit is a **candidate, not a
   commitment**: it is accepted only if it does not *lower* the fact-level faithfulness measure
   (Section 3) relative to the pre-revision unit. This guards against the documented failure that
   "*In 37.0% of the time, the model changes a correct answer into an incorrect one*" during
   self-correction (Xu et al., *Towards Reasoning ... via Multi-Agent Peer Review*, S2 ID
   265157805). Because the summary is already atomic-fact-per-sentence (step 1), the flagged unit
   **is** the unsupported claim — span-level error localization is **structural**, not an inferred
   span on unstructured text, which is exactly the regime in which localization is reliable
   (S_selfloc). This is what raises the gate's ceiling: unlocalized LLM feedback "*tend[s] to
   hallucinate and lack reliability*" and "*the self-correction performance ... is boosted if the
   error location is given*" (Wang et al., *Divide-Verify-Refine*, S2 ID 276725495), and structured
   units give the error location for free. We nonetheless **measure** the residual: span-level
   localization accuracy of the structured units against human-marked spans (Section 3), and gate
   false-accept/false-reject **conditioned on localizer-correct vs. localizer-wrong** cases. We
   acknowledge this gate **bounds rather than resolves** the self-correction risk and that models
   "*struggle to fully incorporate external feedback*" even when it is near-optimal (Feedback
   Friction, S2 ID 279391939); structuring lifts the ceiling, and the conditioned measurement
   shows how much of the remaining gate error is localization vs. scoring.
5. **Termination.** We repeat verify → revise until no unit is flagged at the chosen
   operating point, or three rounds elapse; "*no significant improvement trend is detected with
   more review rounds*" (S2 ID 265157805), motivating the small cap.

## 3. Planned experiments

- **Data and PRE-REGISTERED subset sizes.** 200 recent arXiv papers (cs.CL). We evaluate
  faithfulness **against the source paper** (source-grounded judgement) and report informativeness
  against the abstract. We **pre-register three human-labeled cs.CL subsets** with stated sizes so
  every reliability number is a bounded interval rather than a noisy point estimate (out-of-domain
  transfer to scientific text must be measured, not assumed — even fine-tuned models are "*still
  substantially lower than human performance (64.3 vs 83.3 F1)*" and "*WICE is challenging even for
  fine-tuned models*", S5):
  - **Verifier-calibration subset: n = 300 atomic-fact units** labeled supported vs. hallucinated,
    with human-marked evidence spans, used to calibrate the document-NLI/LLM verifier and to train
    the conv-aggregator threshold (powered so a 95% Wilson interval on precision/recall near 0.8 is
    ≤ ~±0.05).
  - **Retrieval-calibration subset: the same 300 units' human-marked evidence sentences**, used to
    estimate Recall@k with a bootstrap 95% CI.
  - **Judge-calibration subset: n = 50 summaries** for Cohen's κ (carried over from iter4, with its
    κ CI), plus the self-preference-bias measurement below.

- **HEADLINE EXPERIMENT — the grounding-source ablation (isolates the contribution, NOW FOUR ARMS).**
  We hold the **verify–revise loop, the verifier, the operating point, and the summarizer all
  FIXED**, and vary **only the evidence base** the retriever grounds against, across four arms:
  - **Arm A — source-PAPER-internal:** retrieve from the input paper's own chunks (FactGuard).
  - **Arm B — external/open-domain web:** retrieve via RARR-style standard web search, the regime in
    which RARR grounds, since RARR "*requires only a handful of training examples, a large
    language model, and standard web search*" and "*primarily aims to correct ... open domain
    scenarios that lack supporting context in the input prompt*" (Gao et al., *RARR: Researching
    and Revising What Language Models Say*, S2 ID 254247260).
  - **Arm C — entity retrieval:** RFEC-style retrieval of evidence sentences from the original
    document for entity-level correction (Lee et al., *Factual Error Correction for Abstractive
    Summaries Using Entity Retrieval*; system characterized in the survey C4, S2 ID 266725532).
  - **Arm D — curated EXTERNAL scientific source (NEW — the arm that DIRECTLY tests the
    Precision-Grounding distinction):** ground each unit against a **curated external scientific
    corpus** — the paper's **cited-reference abstracts plus a domain abstract corpus** — in the
    canonical SciFact regime where, "*Given a claim c and a collection of candidate abstracts which
    may contain evidence relevant to c*", the system must "*retrieve candidate abstracts from a
    corpus of documents*" (Wadden et al. SciFact task, as described in S2 ID 245130931). This arm
    is the curated-external analogue of Precision Grounding's domain database, so **Arm A vs. Arm D
    tests the paper-INTERNAL-chunks-vs-curated-external-DB distinction DIRECTLY**, rather than
    arguing it.
  The reported quantity is the **faithfulness delta attributable to the evidence base**: (Arm A −
  Arm B), (Arm A − Arm C), and the load-bearing **(Arm A − Arm D)**, on the primary metric, at
  matched abstractiveness. Because the *only* varied factor is the evidence base, any gain is
  attributed to the grounding source rather than to the loop or verifier (shared with all arms).
  We **explicitly position this ablation as EXTENDING, not pre-empting, Precision Grounding**
  (Cheng et al., *Precision Grounding: Augmenting Large Language Models with Evidence-Based
  Databases for Trustworthy Genetic Variant Summarization*, S2 ID 279250142), which already found
  that source-specific grounding "*outperformed web-search grounding*" and "*reduced clinically
  harmful hallucinations*". Our A-vs-D contrast converts the distinction that separates FactGuard
  from Precision Grounding — **paper-INTERNAL chunks of the document being summarized vs. a curated
  EXTERNAL scientific DB** — from an argued claim into a **measured delta**. We also take Precision
  Grounding's finding that "*automated NLP metrics correlated weakly with expert-rated accuracy*"
  as direct **motivation for our human-calibration step**, since our faithfulness numbers are
  automatic and could otherwise diverge from expert judgement on the same source-vs-curated-DB
  comparison.

- **Primary metric — fact-level entailment faithfulness.** Because the summary is already emitted
  as atomic-fact units (Section 2.1), the FActScore decomposition is **native to the pipeline**:
  FActScore "*breaks a generation down into a series of atomic facts and computes a fraction of
  facts supported by a given knowledge source*" with an automatic estimator that tracks the ground
  truth (Min et al., *FActScore*, S2 ID 258841470). We report the **fraction of units entailed by
  the source paper**, adjudicated by the document-level NLI backbone with calibrated SummaC_Conv
  aggregation (Section 2.3), and the **residual unsupported-claim rate** (1 − entailed fraction).
  Because the score "*will differ*" when "*two models decompose the same claim into different
  numbers of atomic claims*" (Wanner et al., *DecMetrics*, S2 ID 281195119) and because FActScore
  assumes "*pieces of information in the knowledge base do not conflict or overlap*" (OpenFActScore,
  S2 ID 280092078) — fragile for hedged scientific claims — we **report the residual rate as an
  interval over two pinned decomposers** (so the band is on the headline number itself) and add a
  **paragraph-level multi-fact consistency check** on top of per-unit entailment.

- **Verifier reliability and the joint residual-rate floor (HEADLINE measurement artifact) — NOW
  WITH CONFIDENCE INTERVALS AND A JOINT-FLOOR-REVEALS-MORE ANALYSIS.** We report, **in one
  protocol**, BOTH floors that bound the residual rate, on the cs.CL domain, **each as a confidence
  interval**:
  (a) **Verifier accuracy on cs.CL, with CIs.** Document-level NLI (with the cs.CL-calibrated
  aggregator) vs. cross-family LLM **precision/recall on the n=300 human-labeled unit set, with 95%
  Wilson confidence intervals**, plus the **MAX vs. mean vs. learned-conv aggregator comparison
  (conv calibrated on cs.CL, stratified by passage length; we adopt the best)**, and the full
  **agreement/disagreement breakdown** at several operating points. We also report the
  **re-ranking-verifier vs. deciding-verifier error-correlation** on the same set (low = the
  feedback loop is genuinely broken, S3) and **span-level localization accuracy of the structured
  units vs. human-marked spans** (the self-correction boost depends on localization being correct,
  S7; structuring is what lifts it, S_selfloc).
  (b) **Lexical-overlap control WITH A HANS-STYLE ADVERSARIAL SLICE.** Performance of a surface
  n-gram-overlap baseline on the same labels, PLUS an explicit **HANS-style adversarial slice of
  non-entailment-with-high-overlap pairs adapted to scientific claims**, since "*the lexical overlap
  heuristic is the assumption that any time all of the words in the hypothesis are also in the
  premise, the label should be entailment ... it fails on many HANS examples*" (McCoy et al.,
  *Syntactic Data Augmentation Increases Robustness to Inference Heuristics*, S2 ID 216553149). This
  demonstrates the NLI verifier's accept decisions are not explained by lexical overlap **on the
  hard cases**, not just on average.
  (c) **Retrieval Recall@k, with a bootstrap CI.** Recall@k of the source-chunk retriever against
  human-marked evidence sentences, reported as a bootstrap 95% CI. A claim whose evidence the
  retriever cannot surface cannot be verified-and-kept, so faithfulness is upper-bounded by
  retriever recall.
  (d) **JOINT-FLOOR-REVEALS-MORE analysis (NEW — makes the bundling empirical, not organizational).**
  We cross-tabulate every human-labeled unit by (within-Recall@k vs. not) × (correctly-verified vs.
  not) and **report the cells the separate floors hide**: in particular (i) units that are
  **within Recall@k but mis-verified** (the retriever surfaced the evidence yet the verifier failed
  — invisible to a recall-only report), and (ii) units **correctly kept only when both floors are
  jointly considered** (e.g. surfaced-and-correctly-judged). Reporting these joint cells shows the
  joint floor reveals failures neither marginal floor does, making the artifact's value empirical.
  We then **define the residual-rate TARGET jointly** — relative to BOTH the measured cs.CL
  verifier-accuracy interval AND the measured Recall@k interval — not the theoretical inevitability
  bound. This single pipeline reporting both floors **as intervals, with the joint cross-tab,** in
  the same protocol on the same domain is the genuinely new measurement artifact (Section 4).

- **Candidate-gate validation.** We report the **gate's own accuracy against human labels**:
  **false-accept** (an edit the gate accepts that a human marks as worse) and **false-reject** (a
  genuine fix the gate blocks), **conditioned on localizer-correct vs. localizer-wrong cases**, so
  the gate is validated rather than trusted and the localization-bottleneck risk is separated from
  scoring error (S2 ID 276725495 / 279391939). We log, per round, how often edits raise vs. lower
  the held-out faithfulness measure.

- **Anti-gaming controls — resisting deletion-gaming AND judge self-preference simultaneously.**
  The **load-bearing controls are coverage + matched abstractiveness**, both cited prior art
  applied (not claimed novel) here. Because faithfulness "*can be trivially raised*" by
  extractiveness or deletion, we report faithfulness at a **matched-abstractiveness operating
  point** on the trade-off curve and add a **coverage/informativeness metric**, so deletion cannot
  win (Ladhak et al., *Faithful or Extractive?*, S2 ID 237364020 — which provides "*a framework
  for evaluating the effective faithfulness ... over a baseline system (control) operating at the
  same level of extractiveness*"); we follow the multi-axis FFCI framing (Koto et al., *FFCI*, S2
  ID 227208867). The same coverage control also guards the **atomic-fact structuring** (Section
  2.1) from gaming faithfulness by shedding content.

- **Secondary, calibrated LLM-judge WITH A DIRECT SELF-PREFERENCE-BIAS MEASUREMENT.** The 1–5
  LLM-judge is **demoted to a calibrated secondary signal only** — never the deciding faithfulness
  measure — because LLM evaluators show "*a prevalent self-preference bias ... where LLM evaluators
  favor their own generations*" (Wu et al., *Do LLM Evaluators Prefer Themselves for a Reason?*, S2
  ID 277622235), amplified in self-refinement pipelines (S2 ID 281080277). Beyond the indirect
  proxies (inter-judge agreement + per-style perplexity), we now **measure the bias DIRECTLY**: we
  compute the **self-preference-bias metric as the judge's score-gap on summaries the judge's own
  model produced vs. summaries from other model families**, holding content/length fixed, so
  "resists self-preference" is measured on the bias itself. Because the bias tracks
  style/perplexity — judges "*assigned higher evaluations to texts with lower perplexity ...
  regardless of whether the text was generated by themselves or not ... the essence of the bias
  lies in perplexity*" (Wataoka et al., *Self-Preference Bias in LLM-as-a-Judge*, S2 ID 273661820)
  — we report the direct bias metric **alongside** per-style summary perplexity and cross-family
  judging under a unified output style, and **calibrate on the 50-summary subset reporting Cohen's
  κ with its confidence interval**. We flag n=50 as small and **bound the reliability claim by
  reporting the κ confidence interval explicitly**.

- **Baselines (head-to-head).** Beyond vanilla single-pass summarization, the four-arm headline
  ablation supplies the **RARR-family web-retrieval baseline** (Arm B), the **RFEC entity-retrieval
  baseline** (Arm C), and the **curated-external-scientific-corpus baseline** (Arm D) under
  identical loop/verifier conditions.

- **Success criterion.** FactGuard (Arm A) achieves a **statistically significant reduction in the
  residual unsupported-claim rate vs. single-pass, vs. the web-retrieval arm (B), vs. the
  entity-retrieval arm (C), AND a measured, signed delta vs. the curated-external-DB arm (D)**, at
  matched abstractiveness and non-decreasing coverage, with the residual rate reported **as an
  interval relative to the jointly measured retriever-recall and cs.CL verifier-accuracy ceilings**.

## 4. Expected contribution

FactGuard's contribution is **not** "first to combine retrieval and self-verification" — that
combination exists (RFEC; the RARR/CoVe/CRITIC verify-revise family, S2 ID 254247260). Nor do we
claim the matched-abstractiveness control, the verify-revise loop, or atomic-fact decomposition as
novel machinery; these are **applied** prior art (Ladhak et al. S2 ID 237364020; RARR S2 ID
254247260; FActScore/Decompose-Then-Verify S2 ID 258841470 / 273821007). We also **do not claim to
be the first to compare source-specific vs. web grounding**: Precision Grounding (S2 ID 279250142)
already reports curated source grounding "*outperformed web-search grounding*". The contribution is:

1. **A precisely-scoped, DEMONSTRATED isolation of source-PAPER-internal grounding that EXTENDS
   Precision Grounding — now tested against a curated external DB directly.** The headline
   **four-arm** ablation holds the loop, verifier, operating point, and summarizer fixed and varies
   only the evidence base — **source-PAPER-internal chunks vs. web vs. entity retrieval vs. a
   curated EXTERNAL scientific corpus (cited-reference abstracts + domain corpus), on scientific-paper
   summarization** — reporting the faithfulness delta attributable to grounding source. The new
   **Arm A vs. Arm D** contrast tests the paper-INTERNAL-chunks-vs-curated-external-DB distinction
   that actually separates FactGuard from Precision Grounding **empirically**, not by argument,
   answering the prior weakness that A>B (source-internal > web) is close to definitional for paper
   summarization. This extends Precision Grounding's curated-clinical-DB-vs-web finding (S2 ID
   279250142) to the paper-internal setting with an automatic, human-free, **human-calibrated**
   protocol — the calibration motivated directly by Precision Grounding's own finding that
   "*automated NLP metrics correlated weakly with expert-rated accuracy*".

2. **A single pipeline that reports BOTH the retrieval recall floor AND the verifier error as
   INTERVALS in the same protocol on the target domain, AND demonstrates the joint floor reveals
   more than its parts — the genuinely new measurement artifact.** Prior single-component papers
   report one or the other. FactGuard jointly reports cs.CL-measured document-NLI verifier accuracy
   **with confidence intervals** (with a cs.CL-calibrated MAX-vs-mean-vs-learned-conv aggregator
   comparison, S2 ID 244345901), a lexical-overlap control **with a HANS-style adversarial slice**
   (S2 ID 216553149 / 233476302), retriever Recall@k **with a bootstrap CI**, the
   re-ranking-vs-deciding error-correlation (decoupling validated by +VeriRel, S2 ID 280671618), and
   structured-unit localization accuracy — then **defines the residual-rate floor jointly as an
   interval** and **empirically demonstrates the joint cross-tab surfaces failures the marginal
   floors hide** (within-Recall@k-but-mis-verified, and only-correct-when-both-considered). This
   converts the joint floor from an organizational claim into a demonstrated artifact.

3. **A faithfulness protocol that resists deletion-gaming AND judge self-preference
   simultaneously, with the self-preference bias measured DIRECTLY.** The load-bearing controls are
   coverage + matched abstractiveness (cited, applied not invented, S2 ID 237364020), which stop
   deletion from winning even under atomic-fact structuring; the demoted, style-unified,
   cross-family LLM-judge is a **calibrated secondary signal only**, with its small-n (n=50)
   reliability **bounded by a reported Cohen's-κ confidence interval**, and — newly — its
   **self-preference bias measured directly as the own-output-vs-other-model score-gap** (S2 ID
   277622235 / 273661820), not merely inferred from inter-judge agreement and perplexity. We do not
   claim novel evaluation machinery — we claim a protocol assembled to be robust on both gaming axes
   at once, with the resistance *measured* on the bias itself.

4. **A structured-summary pipeline that RAISES (not merely measures) the localization ceiling of
   the self-correction gate.** By emitting the summary as atomic-fact-per-sentence units, FactGuard
   moves localization into the regime where it is reliable — LLMs "*self-localize effectively ...
   with structured reasoning traces*" but only "*58%*" agreement on unstructured text (S2 ID
   285271322) — so the candidate gate is no longer bottlenecked by an unreliable auto-localizer.
   This is the soundness change that turns the localization risk from *measured* to *mitigated*.

We position significance as a **practical, quantified mitigation pipeline** — reducing unsupported
claims by a measured margin, with a residual rate reported **as an interval** against the jointly
measured retriever-recall and cs.CL verifier-accuracy ceilings — explicitly *not* a route to
hallucination-free summaries. This is consistent with both the formal inevitability result over
infinite inputs (S2 ID 267069207) and the counter-result that on a fixed benchmark hallucination
probability "*can be made statistically negligible*" with better data and algorithms (S2 ID
276422285).
</content>
</invoke>
