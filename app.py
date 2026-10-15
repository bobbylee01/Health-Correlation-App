import streamlit as st
import pandas as pd
import seaborn as sns


def pair_stats(data, x, y):
    pairs = data[[x, y]].dropna()
    n = len(pairs)
    r = float("nan")
    if n >= 2 and pairs[x].nunique() > 1 and pairs[y].nunique() > 1:
        r = pairs[x].corr(pairs[y])
    return pairs, r, n


def format_r(r):
    return "N/A" if pd.isna(r) else f"{r:.3f}"


def scatter(data, x, y, title, limits=None):
    pairs, r, n = pair_stats(data, x, y)
    st.write(f"**{title}: r = {format_r(r)} | n = {n:,}**")
    if pairs.empty:
        st.info("No valid pairs remain under the current filters.")
        return
    chart = sns.relplot(data=pairs, x=x, y=y, alpha=0.45, height=4, aspect=1.3)
    if limits is not None and not limits.empty:
        for variable, setter in [(x, chart.ax.set_xlim), (y, chart.ax.set_ylim)]:
            low, high = limits[variable].min(), limits[variable].max()
            padding = (high - low) * 0.05 if high > low else 0.5
            setter(low - padding, high + padding)
    chart.ax.set_title(title)
    st.pyplot(chart.figure, clear_figure=True)


@st.cache_data
def load_data():
    data = pd.read_csv("nhanes_health.csv")
    numeric = list(data.select_dtypes(include="number").columns.drop("sex", errors="ignore"))
    data[numeric] = data[numeric].replace([float("inf"), -float("inf")], float("nan"))
    return data, numeric


st.set_page_config(page_title="NHANES Health Explorer", layout="wide")
sns.set_theme(style="whitegrid")
st.title("NHANES Health Measurement Explorer")
st.write("Explore relationships between health measurements in the NHANES participant sample.")
st.caption("Pearson r describes linear association, not causation. A value near zero can hide nonlinear relationships. These unweighted results describe this sample.")
try:
    df, numeric = load_data()
except (OSError, ValueError) as error:
    st.error(f"Could not load nhanes_health.csv: {error}")
    st.stop()

st.sidebar.header("Participant filters")
age_range = st.sidebar.slider("Age range (years)", int(df.age.min()), int(df.age.max()), (int(df.age.min()), int(df.age.max())))
sex = st.sidebar.selectbox("Sex", ["All", "Female", "Male"])
bmi_range = st.sidebar.slider("BMI range (kg/m²)", float(df.bmi.min()), float(df.bmi.max()), (float(df.bmi.min()), float(df.bmi.max())), step=0.1)
filtered = df.loc[df.age.between(*age_range) & df.bmi.between(*bmi_range)]
if sex != "All":
    filtered = filtered.loc[filtered.sex == sex]
st.sidebar.caption("Filters affect every view. Endpoints are included. Rows missing age or BMI cannot satisfy the range filters.")
st.write(f"**Participants after filtering: {len(filtered):,} of {len(df):,}**")
st.caption("Age 80 means 80 or older. Each n counts valid observations for its specific variable pair.")
with st.expander("Preview filtered data"):
    st.dataframe(filtered.head(50), hide_index=True, width="stretch")
if filtered.empty:
    st.info("No participants match. Widen the ranges or select All sexes.")
    st.stop()

st.subheader("1. Correlation heatmap")
correlations = pd.DataFrame(float("nan"), index=numeric, columns=numeric)
annotations = pd.DataFrame("", index=numeric, columns=numeric)
for a in numeric:
    for b in numeric:
        if a == b:
            values = filtered[a].dropna()
            n = len(values)
            r = 1.0 if n >= 2 and values.nunique() > 1 else float("nan")
        else:
            _, r, n = pair_stats(filtered, a, b)
        correlations.loc[a, b] = r
        annotations.loc[a, b] = f"r={format_r(r)}\nn={n:,}"
# Seaborn creates the figure; no additional plotting package is imported.
heatmap = sns.displot(x=[0], height=11, aspect=1.2)
heatmap.ax.clear()
sns.heatmap(correlations.fillna(0), annot=annotations, fmt="", cmap="vlag", vmin=-1, vmax=1, center=0, annot_kws={"size": 8}, ax=heatmap.ax, cbar_kws={"label": "Pearson r"})
heatmap.ax.tick_params(axis="x", labelrotation=45)
heatmap.figure.tight_layout()
st.pyplot(heatmap.figure, clear_figure=True)
st.caption("N/A cells use a neutral background; that background does not indicate a calculated r of zero.")

st.subheader("2. Compare two measurements")
left, right = st.columns(2)
x = left.selectbox("X variable", numeric, index=numeric.index("bmi"))
y_options = [column for column in numeric if column != x]
y = right.selectbox("Y variable", y_options, index=y_options.index("waist_cm") if "waist_cm" in y_options else 0)
scatter(filtered, x, y, f"{x} vs {y}")

st.subheader("3. Pearson correlation and sample size")
_, r, n = pair_stats(filtered, x, y)
st.write(f"**r = {format_r(r)} | n = {n:,}**")
st.caption("Only participants with valid values for both selected measurements are included. Fewer than two pairs or a constant measurement gives r = N/A.")

st.subheader("4. Strongest positive and negative correlations")
records = []
for index, a in enumerate(numeric):
    for b in numeric[index + 1:]:
        _, r, n = pair_stats(filtered, a, b)
        records.append({"Variable 1": a, "Variable 2": b, "r": r, "n": n})
ranking = pd.DataFrame(records)
positive, negative = st.columns(2)
for container, title, subset in [
    (positive, "Strongest positive", ranking.loc[ranking.r > 0].sort_values("r", ascending=False).head(5)),
    (negative, "Strongest negative", ranking.loc[ranking.r < 0].sort_values("r").head(5)),
]:
    container.write(f"**{title}**")
    if subset.empty:
        container.info("No calculable correlations in this direction.")
    else:
        display = subset.copy()
        display["r"] = display["r"].map(format_r)
        container.dataframe(display, hide_index=True, width="stretch")
st.caption("Each pair appears once. Self-correlations, zero correlations, and undefined results are excluded.")

st.subheader("5. Compare females and males")
st.caption("Groups retain every sidebar filter and use the selected variables with shared axis ranges. Selecting one sex leaves the other group empty.")
limits = filtered[[x, y]].dropna()
for container, group in zip(st.columns(2), ["Female", "Male"]):
    with container:
        scatter(filtered.loc[filtered.sex == group], x, y, group, limits)
