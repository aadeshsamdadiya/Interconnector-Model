import pandas as pd
import os

files = [
    "/Users/aadesh/Downloads/GUI_NET_CROSS_BORDER_PHYSICAL_FLOWS_202601010000-202701010000.csv",
    "/Users/aadesh/Downloads/GUI_NET_CROSS_BORDER_PHYSICAL_FLOWS_202501010000-202601010000.csv",
    "/Users/aadesh/Downloads/GUI_NET_CROSS_BORDER_PHYSICAL_FLOWS_202401010000-202501010000.csv",
    "/Users/aadesh/Downloads/GUI_NET_CROSS_BORDER_PHYSICAL_FLOWS_202301010000-202401010000.csv",
    "/Users/aadesh/Downloads/GUI_NET_CROSS_BORDER_PHYSICAL_FLOWS_202201010000-202301010000.csv",
    "/Users/aadesh/Downloads/GUI_NET_CROSS_BORDER_PHYSICAL_FLOWS_202101010000-202201010000.csv",
]

frames = []

for filepath in files:
    if not os.path.exists(filepath):
        print(f"File not found, skipping: {filepath}")
        continue

    df = pd.read_csv(filepath)
    mask = df.apply(lambda row: row.astype(str).str.contains("IFA2", case=False).any(), axis=1)
    filtered = df[mask]
    frames.append(filtered)
    print(f"{os.path.basename(filepath)}: {len(filtered)} IFA2 rows collected")

combined = pd.concat(frames, ignore_index=True)

combined["_sort_key"] = pd.to_datetime(
    combined["MTU"].str.split(" - ").str[0].str.strip(),
    dayfirst=True,
)
combined.sort_values("_sort_key", inplace=True)
combined.drop(columns=["_sort_key"], inplace=True)
combined.reset_index(drop=True, inplace=True)

output_path = "/Users/aadesh/Downloads/GUI_NET_CROSS_BORDER_IFA2_combined.csv"
combined.to_csv(output_path, index=False)
print(f"\nDone: {len(combined)} rows saved to {os.path.basename(output_path)}")
