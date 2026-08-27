from pathlib import Path
import json, math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path.cwd()
FREE = ROOT / 'runs_large/qwen36_27b/free_20260826T104524Z'
REL = ROOT / 'runs_large/qwen36_27b/relevant_clamp_20260826T113732Z'
IRR = ROOT / 'runs_large/qwen36_27b/irrelevant_matched_clamp_20260826T115701Z'
BOUNDARY = Path((ROOT / 'boundary_shift_experiment/LATEST').read_text().strip())
FIG = ROOT / 'figures'
DATA = ROOT / 'figure_data'
DOCS = ROOT / 'docs'
for p in (FIG, DATA, DOCS): p.mkdir(exist_ok=True)
SEED = 382806405
BOOT = 10000

plt.rcParams.update({
    'figure.dpi': 160, 'savefig.dpi': 600, 'font.size': 10,
    'axes.labelsize': 11, 'axes.titlesize': 12,
    'xtick.labelsize': 9, 'ytick.labelsize': 9, 'legend.fontsize': 9,
    'axes.spines.top': False, 'axes.spines.right': False,
    'pdf.fonttype': 42, 'ps.fonttype': 42,
})

def load(path): return json.loads(Path(path).read_text())

def valid(xs):
    return np.asarray([float(x) for x in xs if x is not None and np.isfinite(float(x)) and float(x)>0], dtype=float)

def final_component(rows, key):
    out=[]
    for x in rows:
        if not isinstance(x, dict): continue
        vals=x.get(key) or []
        if not vals: continue
        try: v=float(vals[-1])
        except Exception: continue
        if np.isfinite(v) and v>0: out.append(v)
    return np.asarray(out, dtype=float)

def save(fig, stem):
    for ext in ('pdf','svg','png'):
        kw={'bbox_inches':'tight'}
        if ext=='png': kw['dpi']=600
        fig.savefig(FIG/f'{stem}.{ext}', **kw)
    plt.close(fig)

def directional(run):
    t=float(load(run/'threshold.json')['threshold'])
    est=load(run/'estimates.json')
    a=valid(est['above_good']); b=valid(est['below_good'])
    return float(np.mean(a>t)-np.mean(b>t)), a, b, t

def boot_directional(run, seed):
    point,a,b,t=directional(run); rng=np.random.default_rng(seed); vals=np.empty(BOOT)
    for i in range(BOOT):
        aa=rng.choice(a,len(a),replace=True); bb=rng.choice(b,len(b),replace=True)
        vals[i]=np.mean(aa>t)-np.mean(bb>t)
    return point,float(np.quantile(vals,.025)),float(np.quantile(vals,.975))

def comp_shift(run,key):
    comp=load(run/'components.json')
    a=final_component(comp['above_good'],key); b=final_component(comp['below_good'],key)
    return float(np.median(np.log(a))-np.median(np.log(b))),a,b

def boot_comp(run,key,seed):
    point,a,b=comp_shift(run,key); rng=np.random.default_rng(seed); vals=np.empty(BOOT)
    for i in range(BOOT):
        aa=rng.choice(a,len(a),replace=True); bb=rng.choice(b,len(b),replace=True)
        vals[i]=np.median(np.log(aa))-np.median(np.log(bb))
    return point,float(np.quantile(vals,.025)),float(np.quantile(vals,.975))

def boot_median(x,seed):
    x=valid(x); rng=np.random.default_rng(seed); vals=np.empty(BOOT)
    for i in range(BOOT): vals[i]=np.median(rng.choice(x,len(x),replace=True))
    return float(np.median(x)),float(np.quantile(vals,.025)),float(np.quantile(vals,.975))

def boot_cross(a,b,boundary,seed):
    a=valid(a); b=valid(b); point=float(np.mean(a>boundary)-np.mean(b>boundary)); rng=np.random.default_rng(seed); vals=np.empty(BOOT)
    for i in range(BOOT):
        aa=rng.choice(a,len(a),replace=True); bb=rng.choice(b,len(b),replace=True)
        vals[i]=np.mean(aa>boundary)-np.mean(bb>boundary)
    return point,float(np.quantile(vals,.025)),float(np.quantile(vals,.975))

arms={'Free':FREE,'Relevant clamp':REL,'Irrelevant clamp':IRR}

# Figure 1
rows=[]
for j,(name,run) in enumerate(arms.items()):
    p,l,h=boot_directional(run,SEED+j); rows.append({'arm':name,'directional_leakage':p,'ci_low':l,'ci_high':h})
df=pd.DataFrame(rows); df.to_csv(DATA/'fig1_directional_leakage.csv',index=False)
fig,ax=plt.subplots(figsize=(5.3,3.7),constrained_layout=True)
x=np.arange(len(df)); y=df.directional_leakage.to_numpy(); lo=df.ci_low.to_numpy(); hi=df.ci_high.to_numpy()
ax.errorbar(x,y,yerr=np.vstack([y-lo,hi-y]),fmt='o',markersize=7,capsize=5,linewidth=1.5)
ax.axhline(0,ls='--',lw=1); ax.set_xticks(x); ax.set_xticklabels(df.arm)
ax.set_ylabel('Directional leakage\nP(above threshold | above-good)\n− P(above threshold | below-good)')
ax.set_title('Behavioral value leakage survives the relevant clamp')
for i,v in enumerate(y): ax.annotate(f'{v:+.2f}',(x[i],v),xytext=(0,9),textcoords='offset points',ha='center')
save(fig,'fig1_behavioral_leakage')

# Figure 2
labels={'giraffe_population':'Giraffe population','spots_per_giraffe':'Spots per giraffe'}
rows=[]
for ai,(arm,run) in enumerate(arms.items()):
    for ci,(key,label) in enumerate(labels.items()):
        p,l,h=boot_comp(run,key,SEED+100+10*ai+ci)
        rows.append({'arm':arm,'component':label,'log_median_shift':p,'ci_low':l,'ci_high':h,'multiplicative_ratio':math.exp(p)})
df2=pd.DataFrame(rows); df2.to_csv(DATA/'fig2_component_shift.csv',index=False)
fig,ax=plt.subplots(figsize=(6.0,4.0),constrained_layout=True); pos=np.arange(len(arms)); offs=[-.10,.10]
for ci,label in enumerate(labels.values()):
    sub=df2[df2.component==label].set_index('arm').loc[list(arms)].reset_index(); y=sub.log_median_shift.to_numpy(); lo=sub.ci_low.to_numpy(); hi=sub.ci_high.to_numpy()
    ax.errorbar(pos+offs[ci],y,yerr=np.vstack([y-lo,hi-y]),fmt='o',capsize=4,markersize=6,label=label)
ax.axhline(0,ls='--',lw=1); ax.set_xticks(pos); ax.set_xticklabels(list(arms)); ax.set_ylabel('Above-good − below-good\nlog median component value')
ax.set_title('The clamp removes distortion in the identified premise'); ax.legend(frameon=False)
save(fig,'fig2_component_distortion')

# Boundary data
design=load(BOUNDARY/'design_lock.json'); bcomp=load(BOUNDARY/'components.json'); best=load(BOUNDARY/'estimates.json')
boundaries={'Low':float(design['low']['implied_population_boundary']),'High':float(design['high']['implied_population_boundary'])}
thresholds={'Low':float(design['low']['threshold']),'High':float(design['high']['threshold'])}

# Figure 3
rows=[]
for li,level in enumerate(('Low','High')):
    for ii,incentive in enumerate(('below_good','above_good')):
        key=f'{level.lower()}_{incentive}'; pop=final_component(bcomp[key],'giraffe_population'); med,l,h=boot_median(pop,SEED+200+li*10+ii)
        rows.append({'boundary_level':level,'population_boundary':boundaries[level],'incentive':incentive,'population_median':med,'ci_low':l,'ci_high':h,'n':len(pop)})
df3=pd.DataFrame(rows); df3.to_csv(DATA/'fig3_boundary_tracking.csv',index=False)
fig,ax=plt.subplots(figsize=(5.5,4.1),constrained_layout=True)
for incentive,label in [('below_good','Below-good'),('above_good','Above-good')]:
    sub=df3[df3.incentive==incentive].sort_values('population_boundary'); x=sub.population_boundary.to_numpy(); y=sub.population_median.to_numpy(); lo=sub.ci_low.to_numpy(); hi=sub.ci_high.to_numpy()
    ax.errorbar(x,y,yerr=np.vstack([y-lo,hi-y]),marker='o',capsize=4,linewidth=1.5,label=label)
mn=min(df3.population_boundary.min(),df3.population_median.min()); mx=max(df3.population_boundary.max(),df3.population_median.max())
ax.plot([mn,mx],[mn,mx],ls='--',lw=1,label='Exact boundary tracking')
ax.set_xlabel('Experimentally implied population boundary'); ax.set_ylabel('Median chosen giraffe population'); ax.set_title('Population estimates partially track the moved boundary'); ax.legend(frameon=False)
save(fig,'fig3_boundary_tracking')

# Figure 4
rows=[]
for li,level in enumerate(('Low','High')):
    b=boundaries[level]; a=final_component(bcomp[f'{level.lower()}_above_good'],'giraffe_population'); d=final_component(bcomp[f'{level.lower()}_below_good'],'giraffe_population'); p,l,h=boot_cross(a,d,b,SEED+300+li)
    rows.append({'boundary':level,'population_boundary':b,'effect':p,'ci_low':l,'ci_high':h})
df4=pd.DataFrame(rows); df4.to_csv(DATA/'fig4_population_crossing.csv',index=False)
fig,ax=plt.subplots(figsize=(4.8,3.7),constrained_layout=True); x=np.arange(len(df4)); y=df4.effect.to_numpy(); lo=df4.ci_low.to_numpy(); hi=df4.ci_high.to_numpy()
ax.errorbar(x,y,yerr=np.vstack([y-lo,hi-y]),fmt='o',markersize=7,capsize=5); ax.axhline(0,ls='--',lw=1); ax.set_xticks(x); ax.set_xticklabels(['Low boundary','High boundary'])
ax.set_ylabel('P(population > boundary | above-good)\n− P(population > boundary | below-good)'); ax.set_title('Preference-directed population crossing is suggestive')
save(fig,'fig4_population_crossing')

# Figure 5
rows=[]
for li,level in enumerate(('Low','High')):
    t=thresholds[level]; a=valid(best[f'{level.lower()}_above_good']); d=valid(best[f'{level.lower()}_below_good']); p,l,h=boot_cross(a,d,t,SEED+400+li)
    rows.append({'boundary':level,'threshold':t,'effect':p,'ci_low':l,'ci_high':h})
df5=pd.DataFrame(rows); df5.to_csv(DATA/'fig5_final_crossing.csv',index=False)
fig,ax=plt.subplots(figsize=(4.8,3.7),constrained_layout=True); x=np.arange(len(df5)); y=df5.effect.to_numpy(); lo=df5.ci_low.to_numpy(); hi=df5.ci_high.to_numpy()
ax.errorbar(x,y,yerr=np.vstack([y-lo,hi-y]),fmt='o',markersize=7,capsize=5); ax.axhline(0,ls='--',lw=1); ax.set_xticks(x); ax.set_xticklabels(['Low boundary','High boundary'])
ax.set_ylabel('P(final > threshold | above-good)\n− P(final > threshold | below-good)'); ax.set_title('Final-answer rerouting remains uncertain')
save(fig,'fig5_final_answer_crossing')

# Summary metrics
main=load(ROOT/'main_experiment/main_clamp_analysis.json'); ba=load(BOUNDARY/'boundary_shift_analysis.json')
summary={
 'free_pilot_directional_leakage':directional(FREE)[0],
 'relevant_clamp_directional_leakage':directional(REL)[0],
 'irrelevant_clamp_directional_leakage':directional(IRR)[0],
 'relevant_minus_irrelevant_leakage':main['primary_causal_contrast']['relevant_minus_irrelevant'],
 'carrier_rel_minus_irr_log_delta':main['carrier_component_rel_minus_irr']['median_log_delta_difference_rel_minus_irr'],
 'carrier_rel_minus_irr_ci_low':main['carrier_component_rel_minus_irr']['ci95'][0],
 'carrier_rel_minus_irr_ci_high':main['carrier_component_rel_minus_irr']['ci95'][1],
 'migration_rel_minus_irr_log_delta':main['migration_component_rel_minus_irr']['median_log_delta_difference_rel_minus_irr'],
 'boundary_tracking_ratio':ba['point_estimates']['boundary_following']['mean_tracking_ratio'],
 'boundary_tracking_bootstrap_median':ba['bootstrap']['mean_boundary_tracking_ratio']['median'],
 'boundary_tracking_ci_low':ba['bootstrap']['mean_boundary_tracking_ratio']['ci95'][0],
 'boundary_tracking_ci_high':ba['bootstrap']['mean_boundary_tracking_ratio']['ci95'][1],
 'mean_population_crossing_effect':ba['point_estimates']['incentive_direction_at_each_boundary']['mean_population_crossing_effect'],
 'mean_final_answer_crossing_effect':ba['point_estimates']['incentive_direction_at_each_boundary']['mean_final_answer_crossing_effect'],
}
pd.DataFrame([{'metric':k,'value':v} for k,v in summary.items()]).to_csv(DATA/'summary_metrics.csv',index=False)

captions='''# Figure Captions\n\n## Figure 1 — Behavioral value leakage\nDirectional leakage is P(final above threshold | above-good) minus P(final above threshold | below-good). Error bars are 95% nonparametric bootstrap intervals.\n\n## Figure 2 — Component-level distortion\nAbove-good minus below-good log-median shifts for giraffe population and spots per giraffe. The relevant intervention fixes spots per giraffe at the locked neutral median of 792.5.\n\n## Figure 3 — Boundary tracking\nWith spots per giraffe fixed at 792.5, low/high final-answer thresholds induce low/high population boundaries from neutral population quantiles. Points show median extracted population estimates with 95% bootstrap intervals.\n\n## Figure 4 — Preference-directed population crossing\nDifference between above-good and below-good in the probability that chosen population exceeds each manipulated boundary.\n\n## Figure 5 — Final-answer crossing\nDifference between above-good and below-good in the probability of a final estimate above each manipulated threshold.\n\n## Main interpretation\nThe initially identified high-slack component is preference-sensitive, and fixing it removes its treatment-dependent distortion. Behavioral leakage nevertheless survives. A follow-up boundary manipulation produces suggestive positive population-boundary tracking, but preference-directed crossing remains statistically uncertain at the available sample size.\n'''
(DOCS/'FIGURE_CAPTIONS.md').write_text(captions)

print('\nCreated publication figures:')
for p in sorted(FIG.glob('*')): print(' ',p)
print('\nCreated figure data:')
for p in sorted(DATA.glob('*')): print(' ',p)
print('\nDONE')
