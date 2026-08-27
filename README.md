# Adaptive Value Leakage Forensics

This project investigates how an outcome preference influences intermediate reasoning in a Donation Bet Fermi-estimation setting.

## Research question

Is value leakage mediated by a single biased intermediate premise, or can the behavioral preference effect survive causal removal of an identified reasoning channel?

## Models

- Target model: Qwen/Qwen3.6-27B
- Automated extractor: Qwen/Qwen3.8-27B

The extractor is treated as a measurement tool rather than ground truth. Raw traces were manually spot-checked on deterministic samples.

## Experimental sequence

### 1. Behavioral pilot

The model estimates the total number of black spots on all living giraffes.

Three conditions are compared:

- neutral baseline
- a good outcome if the estimate is below a threshold
- a good outcome if the estimate is above a threshold

### 2. Component attribution

Reasoning traces are decomposed into:

- giraffe population
- spots per giraffe
- candidate/final total

Neutral epistemic slack is measured as IQR(log X).

The highest-slack component was `spots_per_giraffe`.

### 3. Causal clamp

The identified component was fixed at its neutral-baseline median:

792.5 spots per giraffe.

This was compared against an identically phrased irrelevant clamp.

The intervention eliminated treatment-dependent distortion in the identified component, but behavioral value leakage survived.

### 4. Boundary-shift follow-up

With spots per giraffe fixed, the final-answer threshold induces a population decision boundary.

Low and high population boundaries were derived from neutral population quantiles and manipulated experimentally.

Population estimates showed suggestive positive tracking of the moved boundary, but preference-directed crossing remained statistically uncertain at the available sample size.

## Main finding

A preference-sensitive intermediate reasoning channel can be causally removed without eliminating behavioral value leakage.

This rules out a simple single-mediator explanation. The remaining preference effect appears causally redundant or distributed across multiple reasoning degrees of freedom.

The follow-up experiment provides suggestive, but not decisive, evidence for adaptive rerouting through a remaining population variable.

## Repository

- `src/` — experimental and analysis code
- `scripts/` — figure generation
- `figures/` — publication-quality PDF, SVG, and 600-DPI PNG figures
- `figure_data/` — CSV data underlying every figure
- `results/` — frozen design locks and final statistical analyses
- `environment/` — reproducibility environment information
- `docs/` — figure captions

## Reproducibility

Random seed: `382806405`

The main causal intervention was hashed before intervention outcomes were observed.

## Limitations

The component extractor is automated and imperfect, though manually audited on deterministic samples.

The boundary-shift follow-up is suggestive rather than statistically decisive.

The experiments study one Fermi-estimation task and one primary target model.
