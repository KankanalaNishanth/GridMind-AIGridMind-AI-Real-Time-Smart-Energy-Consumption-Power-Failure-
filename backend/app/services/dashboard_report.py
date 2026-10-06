"""
Final summary dashboard (Phase 11 of the original notebook).

Regenerates the same 5-panel matplotlib dashboard — monthly trend,
disruption rate by circle, anomaly split, cluster scatter, SARIMA
forecast — as a static PNG. This is a reporting artifact, not
something the API serves live; run scripts/generate_dashboard.py to
produce it after training.
"""
import logging

import joblib
import matplotlib
matplotlib.use("Agg")  # headless — no display needed
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import pandas as pd

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_STYLE = {
    "figure.facecolor": "#0F0F1A",
    "axes.facecolor": "#1A1A2E",
    "text.color": "white",
    "axes.labelcolor": "white",
    "xtick.color": "white",
    "ytick.color": "white",
    "axes.edgecolor": "#444",
    "axes.grid": True,
    "grid.color": "#333",
    "grid.alpha": 0.4,
}


def generate_final_dashboard(df: pd.DataFrame, output_filename: str = "gridmind_dashboard.png") -> str:
    """Build and save the final analytics dashboard PNG. Returns the output path as a string."""
    settings = get_settings()
    models_dir = settings.models_path

    kmeans_model = joblib.load(models_dir / "kmeans.pkl")
    scaler_kmeans = joblib.load(models_dir / "scaler_kmeans.pkl")
    sarima_res = joblib.load(models_dir / "sarima_model.pkl")

    circle_agg = df.groupby("Circle").agg(
        avg_units=("Units", "mean"),
        total_units=("Units", "sum"),
        avg_connections=("TotServices", "mean"),
        avg_billing_ratio=("billing_ratio", "mean"),
        avg_load_factor=("load_factor", "mean"),
        disruption_rate=("disruption", "mean"),
    ).dropna()
    X_km = scaler_kmeans.transform(circle_agg)
    circle_agg["cluster"] = kmeans_model.predict(X_km)

    # Anomaly labels for the pie chart — recompute the same way training did
    from app.services.ml_pipeline import ISO_FEATURES
    iso_model = joblib.load(models_dir / "iso_forest.pkl")
    scaler_iso = joblib.load(models_dir / "scaler_iso.pkl")
    X_iso = df[ISO_FEATURES].fillna(0)
    df = df.copy()
    df["is_anomaly"] = (iso_model.predict(scaler_iso.transform(X_iso)) == -1).astype(int)

    with plt.rc_context(_STYLE):
        fig = plt.figure(figsize=(18, 12), facecolor="#0F0F1A")
        fig.suptitle("GridMind AI — Final Analytics Dashboard", fontsize=18,
                     color="white", fontweight="bold", y=0.98)
        gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.45, wspace=0.35)

        # 1: Monthly trend
        ax1 = fig.add_subplot(gs[0, :])
        monthly = df.groupby("month_num")["Units"].sum()
        ax1.plot(monthly.index, monthly.values / 1e6, "o-", color="#7F77DD", linewidth=2.5, markersize=6)
        ax1.fill_between(monthly.index, monthly.values / 1e6, alpha=0.15, color="#7F77DD")
        ax1.set_title("Monthly Total Consumption (Million kWh)", color="white")
        ax1.set_xlabel("Month"); ax1.set_ylabel("M kWh")
        for m, v in zip(monthly.index, monthly.values / 1e6):
            ax1.annotate(f"{v:.0f}M", (m, v), textcoords="offset points",
                         xytext=(0, 5), fontsize=7, color="#AAA", ha="center")

        # 2: Disruption rate per circle
        ax2 = fig.add_subplot(gs[1, 0])
        dis = df.groupby("Circle")["disruption"].mean().sort_values()
        cols = ["#D85A30" if v > 0.5 else "#1D9E75" for v in dis.values]
        ax2.barh(range(len(dis)), dis.values * 100, color=cols)
        ax2.set_yticks(range(len(dis)))
        ax2.set_yticklabels([c[:12] for c in dis.index], fontsize=7)
        ax2.axvline(50, color="white", linestyle="--", alpha=0.5)
        ax2.set_title("Disruption Rate % by Circle", color="white", fontsize=10)

        # 3: Anomaly pie
        ax3 = fig.add_subplot(gs[1, 1])
        sizes = [df["is_anomaly"].sum(), (df["is_anomaly"] == 0).sum()]
        ax3.pie(sizes, labels=["Anomaly", "Normal"], colors=["#D85A30", "#1D9E75"],
                autopct="%1.1f%%", startangle=90, textprops={"color": "white", "fontsize": 9})
        ax3.set_title("Anomaly Distribution", color="white", fontsize=10)

        # 4: Cluster scatter
        ax4 = fig.add_subplot(gs[1, 2])
        clr = ["#7F77DD", "#1D9E75", "#D85A30", "#BA7517"]
        for cl in sorted(circle_agg["cluster"].unique()):
            sub = circle_agg[circle_agg["cluster"] == cl]
            ax4.scatter(sub["avg_billing_ratio"], sub["disruption_rate"] * 100,
                        s=80, c=clr[cl % len(clr)], label=f"C{cl}", zorder=5)
        ax4.set_title("Circle Clusters", color="white", fontsize=10)
        ax4.set_xlabel("Billing Ratio", fontsize=8); ax4.set_ylabel("Disruption %", fontsize=8)
        ax4.legend(fontsize=7)

        # 5: SARIMA forecast
        ax5 = fig.add_subplot(gs[2, :])
        fc = sarima_res.get_forecast(steps=settings.SARIMA_FORECAST_STEPS)
        fc_vals = fc.predicted_mean
        fc_ci = fc.conf_int(alpha=0.2)
        last_idx = monthly.index[-1]
        fmonths = list(range(last_idx + 1, last_idx + 1 + settings.SARIMA_FORECAST_STEPS))
        ax5.plot(monthly.index, monthly.values / 1e6, "o-", color="#7F77DD", linewidth=2, label="Actual")
        ax5.plot(fmonths, fc_vals.values / 1e6, "s--", color="#1D9E75", linewidth=2, label="SARIMA Forecast")
        ax5.fill_between(fmonths, fc_ci.iloc[:, 0].values / 1e6, fc_ci.iloc[:, 1].values / 1e6,
                         alpha=0.2, color="#1D9E75", label="80% CI")
        ax5.axvline(last_idx + 0.5, color="#D85A30", linestyle=":", linewidth=1.5)
        ax5.set_title("6-Month Demand Forecast", color="white", fontsize=10)
        ax5.set_xlabel("Month"); ax5.set_ylabel("M kWh")
        ax5.legend(fontsize=8)

        output_path = settings.reports_path / output_filename
        plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="#0F0F1A")
        plt.close(fig)

    logger.info("Final dashboard saved to %s", output_path)
    return str(output_path)
