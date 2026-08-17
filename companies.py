import pandas as pd


class CompanyBook:
    def __init__(self, path="real_pro_av_companies.xlsx"):
        self.path = path
        self.df = pd.read_excel(path)
        self._prepare()

    def _prepare(self):
        self.df["Last Checked Date"] = pd.to_datetime(
            self.df["Last Checked Date"], errors="coerce"
        )
        # Empty Excel cells load as float, which rejects bools and strings
        self.df["is_risk"] = self.df["is_risk"].astype(object)
        self.df["Risk_Reason"] = self.df["Risk_Reason"].astype(object)
        self.df["Last Risk Eval"] = pd.to_datetime(
            self.df["Last Risk Eval"], errors="coerce"
        )

    def get_vendors(self, run_count):
        batch = self.df.sort_values(
            "Last Checked Date", ascending=True, na_position="first"
        ).head(run_count)
        return batch["Company / Brand"].tolist()

    def update_research_date(self, vendor):
        row = self.df["Company / Brand"] == vendor
        self.df.loc[row, "Last Checked Date"] = pd.Timestamp.now().floor("s")
        self.save()
        print(f"Updated Last Checked Date for {vendor}")

    def update_risk_fields(self, vendor, decision):
        row = self.df["Company / Brand"] == vendor
        self.df.loc[row, "is_risk"] = decision.is_risk
        self.df.loc[row, "Risk_level"] = decision.Risk_level
        self.df.loc[row, "Risk_Reason"] = decision.Risk_Reason
        self.df.loc[row, "Last Risk Eval"] = pd.Timestamp.now().floor("s")
        self.save()
        print(
            f"Updated risk fields for {vendor}: "
            f"level={decision.Risk_level}, is_risk={decision.is_risk}"
        )

    def save(self):
        self.df.to_excel(self.path, index=False)


if __name__ == "__main__":
    book = CompanyBook()
    vendors = book.get_vendors(3)
    print(vendors)
