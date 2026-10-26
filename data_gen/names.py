"""Fixed generic name lists for synthetic data. No real company or customer names."""

BUSINESS_UNITS = [
    "Agent Operations", "Brokerage", "Safety and Compliance", "Finance",
    "Capacity and Carrier Relations", "Customer Solutions", "Technology",
    "Claims and Insurance", "Human Resources", "Marketing",
]

SYSTEMS = [
    "TMS", "ERP", "CRM", "Load Board", "ELD Telematics", "Data Warehouse",
    "Document Management", "Agent Portal", "Claims System", "Payroll System",
    "Fuel Card Platform", "Email",
]

VENDORS = [
    "Telematics Provider", "Fuel Card Provider", "Factoring Partner",
    "Insurance Broker", "Load Board Provider", "Payroll Provider",
]

FIRST_NAMES = ["Alex", "Blair", "Casey", "Dana", "Emery", "Finley", "Gray", "Harper",
               "Indy", "Jordan", "Kai", "Logan", "Morgan", "Noel", "Parker", "Quinn",
               "Reese", "Sage", "Taylor", "Val"]
LAST_NAMES = ["Adams", "Brooks", "Carter", "Diaz", "Ellis", "Foster", "Garcia", "Hayes",
              "Irwin", "James", "Khan", "Lopez", "Miller", "Nguyen", "Owens", "Patel",
              "Reed", "Shah", "Turner", "Young"]
EMAIL_DOMAIN = "example.com"

PAINS = ["This takes several people many hours each week.", "Errors here cost us money every month.",
         "Agents have asked for this repeatedly.", "Leadership wants better visibility here.",
         "Turnaround time is too slow for customers."]
BENEFITS = ["Save staff hours each week", "Reduce costly errors", "Faster answers for agents",
            "Better decisions with current data", "Lower risk exposure", "Improve customer experience"]

# Category templates; {s}=subject, {d}=data hint.
PATTERNS = {
    "Generative AI Assistant": [
        ("Assistant that answers questions about {s}", "Staff spend hours looking up {s}. A chat assistant over {d} would answer common questions in plain language."),
        ("Copilot to summarize {s}", "Generate short written summaries of {s} from {d} so managers do not read every record."),
    ],
    "Predictive Analytics": [
        ("Forecast {s}", "Build a model on {d} to forecast {s} for the next quarter so teams can plan ahead."),
        ("Predictive score for {s}", "Score every record for {s} risk using {d} so the team works the highest scores first."),
    ],
    "Process Automation": [
        ("Automate the {s} workflow", "The {s} process is manual today and relies on email and spreadsheets. Automate the routing and approvals using {d}."),
        ("Rules bot for {s}", "A rules-based bot that checks {d} and completes routine {s} steps without a person touching them."),
    ],
    "Data Integration": [
        ("Pipeline to centralize {s} data", "{d} lives in separate systems. Build a governed pipeline that lands it in one curated table for {s}."),
        ("Sync {s} between systems", "Keep {d} in sync across systems automatically so {s} numbers match everywhere."),
    ],
    "Reporting and BI": [
        ("Dashboard for {s}", "Leaders cannot see {s} trends. Publish a self-serve dashboard on {d} with weekly refresh."),
        ("Monthly scorecard on {s}", "Create a standard monthly scorecard of {s} from {d} for business unit reviews."),
    ],
    "Document Intelligence": [
        ("Extract data from {s} documents", "Paperwork for {s} is keyed by hand. Read the documents and extract fields from {d} automatically."),
        ("Classify incoming {s} paperwork", "Sort and classify incoming {s} files from {d} so they reach the right queue."),
    ],
    "Risk and Compliance Analytics": [
        ("Risk alerts for {s}", "Detect unusual patterns in {d} related to {s} and alert the responsible team early."),
        ("Compliance monitoring of {s}", "Monitor {s} against policy using {d} and report exceptions for audit."),
    ],
}

# (subject, data hint, typical systems). Topics used by planted pairs are excluded.
SUBJECTS = [
    ("trailer utilization", "trailer location pings", ["ELD Telematics", "TMS"]),
    ("agent recruiting", "agent applications", ["CRM", "Agent Portal"]),
    ("quick pay requests", "carrier payment requests", ["ERP", "TMS"]),
    ("accessorial charges", "billing line items", ["TMS", "ERP"]),
    ("load tendering", "tender acceptance history", ["TMS", "Load Board"]),
    ("oversize load permits", "permit applications", ["Document Management", "TMS"]),
    ("roadside inspections", "inspection reports", ["ELD Telematics", "Document Management"]),
    ("shipper onboarding", "new customer forms", ["CRM", "ERP"]),
    ("agent training completion", "learning records", ["Agent Portal", "Payroll System"]),
    ("cargo theft", "incident reports", ["Claims System", "ELD Telematics"]),
    ("equipment maintenance", "work orders", ["ELD Telematics", "ERP"]),
    ("customer churn", "shipment volume by customer", ["CRM", "TMS"]),
    ("driver referral bonuses", "referral records", ["Payroll System", "CRM"]),
    ("tolls and fees", "toll transactions", ["Fuel Card Platform", "ERP"]),
    ("weather disruptions", "route and weather feeds", ["TMS", "Data Warehouse"]),
    ("cross-border paperwork", "customs forms", ["Document Management", "TMS"]),
    ("hazmat shipments", "hazmat declarations", ["TMS", "Document Management"]),
    ("agent territory coverage", "agent locations and lanes", ["Agent Portal", "TMS"]),
    ("accounts receivable aging", "open invoices", ["ERP", "CRM"]),
    ("carrier scorecards", "on-time and claims history", ["TMS", "Claims System"]),
    ("dock appointment scheduling", "appointment requests", ["TMS", "Email"]),
    ("lumper receipts", "receipt images", ["Document Management", "ERP"]),
    ("spot market bids", "bid history", ["Load Board", "TMS"]),
    ("trailer pool balancing", "trailer inventory by yard", ["TMS", "ELD Telematics"]),
    ("workers compensation claims", "injury reports", ["Claims System", "Payroll System"]),
    ("agent contract renewals", "agent agreements", ["Document Management", "CRM"]),
    ("customer service call volume", "call logs", ["CRM", "Email"]),
    ("empty miles", "trip mileage records", ["ELD Telematics", "TMS"]),
    ("vendor payments", "accounts payable entries", ["ERP", "Email"]),
    ("security badge access", "facility access logs", ["Data Warehouse", "ERP"]),
    ("marketing campaign leads", "web form leads", ["CRM", "Email"]),
    ("tire and parts spend", "parts purchase orders", ["ERP", "Fuel Card Platform"]),
    ("seasonal capacity planning", "historical load volume", ["TMS", "Data Warehouse"]),
    ("chargeback disputes", "dispute tickets", ["ERP", "CRM"]),
    ("new hire paperwork", "employee onboarding forms", ["Payroll System", "Document Management"]),
    ("load board posting quality", "posted load details", ["Load Board", "TMS"]),
    ("cargo insurance renewals", "policy documents", ["Document Management", "Claims System"]),
    ("agent sales pipeline", "opportunity records", ["CRM", "Agent Portal"]),
    ("idle engine time", "engine telemetry", ["ELD Telematics", "Data Warehouse"]),
    ("expense report audits", "employee expenses", ["ERP", "Email"]),
    ("customer rate requests", "quote emails", ["Email", "CRM"]),
    ("flatbed securement checks", "securement photos", ["Document Management", "ELD Telematics"]),
    ("legal hold requests", "email and document archives", ["Email", "Document Management"]),
    ("IT help desk tickets", "ticket history", ["Data Warehouse", "Email"]),
    ("warehouse partner performance", "partner service levels", ["TMS", "CRM"]),
    ("agent payout timing", "settlement runs", ["Payroll System", "ERP"]),
    ("freight mode selection", "shipment characteristics", ["TMS", "Data Warehouse"]),
    ("carrier fraud signals", "carrier profile changes", ["TMS", "CRM"]),
    ("shipment visibility notifications", "status updates", ["TMS", "Email"]),
    ("data quality in the TMS", "duplicate and missing records", ["TMS", "Data Warehouse"]),
    ("fleet emissions reporting", "fuel and mileage data", ["Fuel Card Platform", "ELD Telematics"]),
    ("budget variance", "general ledger actuals", ["ERP", "Data Warehouse"]),
    ("customer contract terms", "signed contracts", ["Document Management", "CRM"]),
    ("agent satisfaction surveys", "survey responses", ["Agent Portal", "Email"]),
    ("brokerage margin leakage", "load-level margins", ["TMS", "ERP"]),
]
