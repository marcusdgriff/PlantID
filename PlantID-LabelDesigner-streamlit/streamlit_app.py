import streamlit as st
import pandas as pd
import io
import os
import pypdfium2 as pdfium

from reportlab.lib.pagesizes import mm, A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.graphics.barcode import qr
from reportlab.graphics.barcode import code128
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing
from reportlab.pdfbase.pdfmetrics import stringWidth

# ======================================================
# Session state for dataset (NEW)
# ======================================================
if "df" not in st.session_state:
    st.session_state.df = None
if "data_source" not in st.session_state:
    st.session_state.data_source = None

# ======================================================
# Draw a single label directly onto a ReportLab canvas
# ======================================================
def draw_label_on_canvas(
    c,
    df_row,
    x,
    y,
    visible_columns,
    code_column,
    code_type="QR",
    highlight_column=None,
    label_width=70,
    label_height=35,
    qr_size=18,
    barcode_width=25,
    barcode_height=10,
    row_height_factor=0.9,
    sidebar_factor=0.25,
    highlight_padding=2,
    padding=4,
    show_border=True,
    show_column_names=True,
    side_highlight=False,
    qr_left_offset=2,
):
    lw_pt = label_width * mm
    lh_pt = label_height * mm
    pad_pt = padding * mm

    # ---- 1. Outer border ----
    if show_border:
        c.saveState()
        c.setStrokeColor(colors.lightgrey)
        c.setLineWidth(0.5)
        c.rect(x, y, lw_pt, lh_pt, stroke=1, fill=0)
        c.restoreState()

    # ---- 2. Sidebar Logic (Isolated with saveState) ----
    side_col_width = 0
    if side_highlight and highlight_column:
        side_col_width = lw_pt * sidebar_factor
        col_name = highlight_column
        value = str(df_row[highlight_column])
        font_size = 6

        # Calculate sidebar geometry
        val_w = stringWidth(value, "Helvetica-Bold", font_size) + highlight_padding
        nam_w = stringWidth(f"{col_name}:", "Helvetica-Oblique", font_size)
        gap = 1 * mm
        total_h = nam_w + gap + val_w
        sidebar_bottom = y + (lh_pt - total_h) / 2

        # Draw Side Label text
        c.saveState()
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Oblique", font_size)
        c.translate(x + side_col_width / 2, sidebar_bottom + nam_w / 2)
        c.rotate(90)
        c.drawCentredString(0, 0, f"{col_name}:")
        c.restoreState()

        # Draw Side Value Box
        val_rect_y = sidebar_bottom + nam_w + gap
        c.saveState()
        c.setFillColor(colors.black)
        c.rect(x, val_rect_y, side_col_width, val_w, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", font_size)
        c.translate(x + side_col_width / 2, val_rect_y + val_w / 2)
        c.rotate(90)
        c.drawCentredString(0, 0, value)
        c.restoreState()

    # ---- 3. Code (QR/Barcode) Logic ----
    code_x = x + side_col_width + (qr_left_offset * mm)
    text_x = x + side_col_width + pad_pt

    if code_column is not None and code_type != "None":
        val = str(df_row[code_column])
        
        if code_type == "QR":
            qr_pt = qr_size * mm
            code_y = y + (lh_pt - qr_pt) / 2
            qrobj = qr.QrCodeWidget(val)
            b = qrobj.getBounds()
            scale = qr_pt / max(b[2]-b[0], b[3]-b[1])
            d = Drawing(qr_pt, qr_pt, transform=[scale, 0, 0, scale, 0, 0])
            d.add(qrobj)
            renderPDF.draw(d, c, code_x, code_y)
            text_x = code_x + qr_pt + 2 * mm

        elif code_type == "Barcode":
            bw_pt = barcode_width * mm
            bh_pt = barcode_height * mm
            code_y = y + (lh_pt - bh_pt) / 2
            
            # Draw directly to canvas (Corrected from previous Drawing approach)
            bc = code128.Code128(
                val, 
                barHeight=bh_pt, 
                barWidth=bw_pt / max(len(val) * 11, 1), 
                humanReadable=False
            )
            bc.drawOn(c, code_x, code_y)
            text_x = code_x + bw_pt + 2 * mm

    # ---- 4. Text Rows Logic ----
    row_count = max(len(visible_columns), 1)
    row_height = ((lh_pt - 2 * pad_pt) / row_count) * row_height_factor
    text_y_start = y + lh_pt - pad_pt - row_height * 0.1
    avail_w = lw_pt - (text_x - x) - pad_pt

    for idx, col_name in enumerate(visible_columns):
        val = str(df_row[col_name])
        y_pos = text_y_start - idx * row_height
        
        c.saveState()
        if show_column_names:
            c.setFont("Helvetica-Oblique", 7)
            c.setFillColor(colors.black)
            c.drawRightString(text_x + avail_w * 0.35, y_pos, f"{col_name}:")

        if col_name == highlight_column:
            c.setFont("Helvetica-Bold", 7)
            v_w = stringWidth(val, "Helvetica-Bold", 7) + highlight_padding
            c.setFillColor(colors.black)
            c.rect(text_x + avail_w * 0.4 - 2, y_pos - 2, v_w, 8, fill=1)
            c.setFillColor(colors.white)
            c.drawString(text_x + avail_w * 0.4, y_pos, val)
        else:
            c.setFont("Helvetica", 7)
            c.setFillColor(colors.black)
            c.drawString(text_x + avail_w * 0.4, y_pos, val)
        c.restoreState()

# ======================================================
# Multi-label PDF sheet
# ======================================================
def generate_sheet_direct(
    df,
    visible_columns,
    code_column,
    code_type,
    highlight_column,
    label_width,
    label_height,
    qr_size,
    barcode_width,
    barcode_height,
    row_height_factor,
    sidebar_factor,
    highlight_padding,
    show_border=True,
    show_column_names=True,
    side_highlight=False,
    qr_left_offset=2,
    page_format="LabelPrinter",
):
    # Page size logic
    if page_format == "A4":
        page_width, page_height = A4
        margin = 5 * mm
    elif page_format == "Letter":
        from reportlab.lib.pagesizes import letter
        page_width, page_height = letter
        margin = 5 * mm
    elif page_format == "LabelPrinter":
        # Exact label size, no margin
        page_width = label_width * mm
        page_height = label_height * mm
        margin = 0
    else:
        page_width, page_height = A4
        margin = 5 * mm

    c = canvas.Canvas("multi_labels.pdf", pagesize=(page_width, page_height))

    x = margin
    y = page_height - label_height * mm - margin

    for _, row in df.iterrows():
        draw_label_on_canvas(
            c, row, x, y,
            visible_columns,
            code_column,
            code_type,
            highlight_column,
            label_width,
            label_height,
            qr_size,
            barcode_width,
            barcode_height,
            row_height_factor,
            sidebar_factor,
            highlight_padding,
            show_border=show_border,
            show_column_names=show_column_names,
            side_highlight=side_highlight,
            qr_left_offset=qr_left_offset,
        )

        x += label_width * mm + margin
        if x + label_width * mm > page_width:
            x = margin
            y -= label_height * mm + margin
            if y < margin:
                c.showPage()
                x = margin
                y = page_height - label_height * mm - margin

    c.save()
    return "multi_labels.pdf"

# ======================================================
# Streamlit UI
# ======================================================
st.set_page_config(layout="wide")
st.title("PlantID Label Designer")

# ======================
# Start page (UPDATED)
# ======================
if st.session_state.df is None:
    st.subheader("Start")

    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Use example dataset"):
            example_path = os.path.join(os.path.dirname(__file__), "PV1_metadata.csv")
            st.session_state.df = pd.read_csv(example_path)
            st.session_state.data_source = "Example dataset"
            st.rerun()

    if uploaded_file:
        st.session_state.df = pd.read_csv(uploaded_file)
        st.session_state.data_source = "Uploaded CSV"
        st.rerun()

    st.info("Upload a CSV or use the example dataset to begin.")
    st.stop()

df = st.session_state.df

# ======================
# Dataset controls (NEW)
# ======================
st.subheader("Dataframe summary")

c1, c2, c3 = st.columns(3)
c1.metric("Rows", len(df))
c2.metric("Columns", df.shape[1])
c3.metric("Source", st.session_state.data_source)

with st.expander("Dataframe preview"):
    summary_df = pd.DataFrame({
        "Column Name": df.columns,
        "Count": df.notna().sum().values
    })
    st.dataframe(summary_df, use_container_width=True)
    
with st.expander("Dataframe controls"):
    st.warning("This will clear the current dataframe and return you to the start page.")

    if st.button("Clear dataframe and restart"):
        st.session_state.df = None
        st.session_state.data_source = None
        st.rerun()

# ---- Sidebar ----
st.sidebar.title("Label Setup")

st.sidebar.header("Data fields")
visible_columns = st.sidebar.multiselect(
    "Columns to display",
    df.columns.tolist(),
    default=df.columns.tolist()[:0],
)

row_index = st.sidebar.number_input(
    "Preview row",
    min_value=1,
    max_value=len(df),
    value=1,
) - 1

# ---- Label size ----
st.sidebar.header("Label size")

LABEL_PRESETS = {
    "Custom": None,
    "Cryovial (25 × 12 mm / 1 × 0.47)": (25, 12),
    "Small Label (25 × 67 mm / 1 × 2.625)": (67, 25),
    "Wristband Label (25 × 254 mm / 1 × 10)": (254, 25),
    "Small Plant Tag (50 × 25 mm / 1.97 × 0.98)": (50, 25),
    "Cryobox / Tube (30 × 15 mm / 1.18 × 0.59)": (30, 15),
    "General Purpose (76 × 25 mm / 3 × 1)": (76, 25),
    "Food Label (76 × 51 mm / 3 × 2)": (76, 51),
    "Tag Label (57 × 102 mm / 2.25 × 4)": (57, 102),
    "Standard Plant Label (70 × 35 mm / 2.76 × 1.38)": (70, 35),
    "Large Field Label (90 × 45 mm / 3.54 × 1.77)": (90, 45),
    "Shipping Label (102 × 152 mm / 4 × 6)": (102, 152),
    "Square Label (51 × 51 mm / 2 × 2)": (51, 51),
}

preset = st.sidebar.selectbox("Preset", list(LABEL_PRESETS.keys()))
if preset == "Custom":
    label_width = st.sidebar.slider("Width (mm)", 10, 140, 70)
    label_height = st.sidebar.slider("Height (mm)", 10, 140, 35)
else:
    label_width, label_height = LABEL_PRESETS[preset]

# ---- Code options ----
st.sidebar.header("Code")

code_type = st.sidebar.selectbox(
    "Code type",
    ["QR", "Barcode", "None"],
    index=0,
)

if code_type != "None":
    code_column = st.sidebar.selectbox("Code column", df.columns.tolist())
else:
    code_column = None

if code_type == "QR":
    qr_size = st.sidebar.slider(
        "QR size (mm)", 8, max(8, label_height - 2), min(18, label_height - 2)
    )
    barcode_width = 0
    barcode_height = 0

elif code_type == "Barcode":
    barcode_width = st.sidebar.slider("Barcode width (mm)", 15, label_width - 5, 25)
    barcode_height = st.sidebar.slider("Barcode height (mm)", 5, label_height - 5, 10)
    qr_size = 0

else:
    qr_size = 0
    barcode_width = 0
    barcode_height = 0

qr_left_offset = st.sidebar.slider("Code left offset (mm)", 0, int(label_width / 2), 2)

# ---- Design ----
st.sidebar.header("Design")
show_column_names = st.sidebar.checkbox("Show column names", True)
row_height_factor = st.sidebar.slider("Row height factor", 0.1, 1.5, 0.9)

highlight_column = st.sidebar.selectbox(
    "Highlight column", ["None"] + df.columns.tolist()
)
highlight_column = None if highlight_column == "None" else highlight_column

if highlight_column:
    highlight_padding = st.sidebar.slider("Highlight padding", 0, 20, 2)
    side_highlight = st.sidebar.checkbox("Side strip highlight", False)
else:
    highlight_padding = 0
    side_highlight = False

sidebar_factor = (
    st.sidebar.slider("Sidebar width factor", 0.05, 0.5, 0.1)
    if side_highlight
    else 0
)

show_border = st.sidebar.checkbox("Show border", True)

# ---- Preview ----
st.subheader("Live preview")

buffer = io.BytesIO()
c_prev = canvas.Canvas(buffer, pagesize=(label_width * mm, label_height * mm))

draw_label_on_canvas(
    c_prev,
    df.iloc[row_index],
    0, 0,
    visible_columns,
    code_column,
    code_type,
    highlight_column,
    label_width,
    label_height,
    qr_size,
    barcode_width,
    barcode_height,
    row_height_factor,
    sidebar_factor,
    highlight_padding,
    show_border=show_border,
    show_column_names=show_column_names,
    side_highlight=side_highlight,
    qr_left_offset=qr_left_offset,
)
c_prev.save()
buffer.seek(0)

pdf = pdfium.PdfDocument(buffer)
pil_image = pdf[0].render(scale=3).to_pil()
st.image(pil_image, caption=f"Previewing Row {row_index + 1}")

# ======================
# Export PDF
# ======================
st.subheader("Export Labels / PDF")

# ---- Page size / printer selector ----
page_format = st.selectbox(
    "Page size / printer",
    ["A4", "Letter", "LabelPrinter"],
    index=2
)

# ---- Generate button ----
if st.button("Generate Multi-Label PDF"):
    pdf_path = generate_sheet_direct(
        df,
        visible_columns,
        code_column,
        code_type,
        highlight_column,
        label_width,
        label_height,
        qr_size,
        barcode_width,
        barcode_height,
        row_height_factor,
        sidebar_factor,
        highlight_padding,
        show_border=show_border,
        show_column_names=show_column_names,
        side_highlight=side_highlight,
        qr_left_offset=qr_left_offset,
        page_format=page_format,
    )
    st.success("PDF generated")
    st.download_button(
        "Download PDF",
        data=open(pdf_path, "rb"),
        file_name=f"multi_labels_{page_format}.pdf",
        mime="application/pdf",
    )