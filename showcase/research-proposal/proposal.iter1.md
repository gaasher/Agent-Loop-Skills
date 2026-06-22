# FactGuard: Retrieval-Augmented Self-Verification for Hallucination-Free Scientific Summarization

## 1. Problem

Large language models (LLMs) are increasingly used to summarize scientific papers, but they
routinely **hallucinate** — stating findings, numbers, or causal claims that the source paper
does not support. In a scientific setting these errors are especially damaging: a fabricated
effect size or an invented citation can propagate into downstream literature reviews and
decisions. We want LLM-generated scientific summaries that are **faithful by construction** —
every claim in the summary traceable to the source.

## 2. Proposed methodology

We propose **FactGuard**, a two-agent pipeline that iteratively removes unsupported claims:

1. **Summarizer.** A summarizer LLM produces a draft summary of the input paper.
2. **Retriever.** For each sentence in the draft, we embed the sentence and retrieve the
   top-k most similar passages from the source paper (dense retrieval over the paper's own
   chunks).
3. **Verifier.** A verifier LLM — the same base model as the summarizer — judges whether each
   draft sentence is *supported*, *contradicted*, or *not addressed* by its retrieved
   passages, and flags every sentence that is not clearly supported.
4. **Revision loop.** The summarizer rewrites or deletes the flagged sentences. We repeat
   verify → revise until the verifier flags nothing, or three rounds elapse.

The core hypothesis is that grounding each claim in retrieved source passages and having the
model check its own draft against that evidence will drive hallucination toward zero without
human intervention.

## 3. Planned experiments

- **Data.** 200 recent arXiv papers (cs.CL), each paired with its abstract as a reference
  summary.
- **System.** A single instruction-tuned LLM plays both summarizer and verifier roles.
- **Primary metric.** We will measure faithfulness with an **LLM-as-judge**: a strong LLM
  reads the paper and the summary and rates faithfulness on a 1–5 scale. We report the mean
  judge score.
- **Comparison.** We compare FactGuard against vanilla single-pass summarization by the same
  model, and expect a higher mean judge score.
- **Success criterion.** FactGuard reaches a mean LLM-judge faithfulness ≥ 4.5/5 and beats the
  vanilla baseline.

## 4. Expected contribution

FactGuard will be the first system to combine retrieval and self-verification into an
automatic, human-free loop for faithful scientific summarization, demonstrating that LLMs can
reliably police their own hallucinations.
