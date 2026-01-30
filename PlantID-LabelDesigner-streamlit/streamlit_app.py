import streamlit as st
import pandas as pd
import io
import os
import pypdfium2 as pdfium

from reportlab.lib.pagesizes import mm, A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.graphics.barcode import qr
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
    qr_column,
    highlight_column=None,
    label_width=70,
    label_height=35,
    qr_size=18,
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
    qr_pt = qr_size * mm

    if show_border:
        c.setStrokeColor(colors.lightgrey)
        c.setLineWidth(0.5)
        c.rect(x, y, lw_pt, lh_pt, stroke=1, fill=0)

    row_count = max(len(visible_columns), 1)
    row_height = ((lh_pt - 2 * pad_pt) / row_count) * row_height_factor
    text_y_start = y + lh_pt - pad_pt - row_height * 0.1

    side_col_width = 0
    if side_highlight and highlight_column:
        side_col_width = lw_pt * sidebar_factor

        col_name = highlight_column
        value = str(df_row[highlight_column])

        font_size = 6
        font_value = "Helvetica-Bold"
        font_name = "Helvetica-Oblique"

        value_width = stringWidth(value, font_value, font_size) + highlight_padding
        name_width = stringWidth(f"{col_name}:", font_name, font_size)
        gap = 1 * mm
        total_height = name_width + gap + value_width
        sidebar_bottom = y + (lh_pt - total_height) / 2

        c.setFillColor(colors.black)
        c.setFont(font_name, font_size)
        c.saveState()
        c.translate(x + side_col_width / 2, sidebar_bottom + name_width / 2)
        c.rotate(90)
        c.drawCentredString(0, 0, f"{col_name}:")
        c.restoreState()

        value_rect_y = sidebar_bottom + name_width + gap
        c.setFillColor(colors.black)
        c.rect(x, value_rect_y, side_col_width, value_width, fill=1, stroke=0)

        c.setFillColor(colors.white)
        c.setFont(font_value, font_size)
        c.saveState()
        c.translate(x + side_col_width / 2, value_rect_y + value_width / 2)
        c.rotate(90)
        c.drawCentredString(0, 0, value)
        c.restoreState()

    if qr_column is not None and qr_size > 0:
        qr_x = x + qr_left_offset * mm
        qr_y = y + (lh_pt - qr_pt) / 2
        qr_value = str(df_row[qr_column])

        qrobj = qr.QrCodeWidget(qr_value)
        bounds = qrobj.getBounds()
        scale = qr_pt / max(bounds[2] - bounds[0], bounds[3] - bounds[1])

        d = Drawing(qr_pt, qr_pt, transform=[scale, 0, 0, scale, 0, 0])
        d.add(qrobj)
        renderPDF.draw(d, c, qr_x, qr_y)

        text_x = qr_x + qr_pt + 4 * mm
    else:
        text_x = x + pad_pt

    available_width = lw_pt - (text_x - x) - pad_pt

    for idx, col_name in enumerate(visible_columns):
        value = str(df_row[col_name])
        y_pos = text_y_start - idx * row_height

        if show_column_names:
            c.setFont("Helvetica-Oblique", 7)
            c.setFillColor(colors.black)
            c.drawRightString(text_x + available_width / 3, y_pos, f"{col_name}:")

        if col_name == highlight_column:
            value_width = stringWidth(value, "Helvetica-Bold", 7) + highlight_padding
            rect_x = text_x + 2 / 3 * available_width - value_width / 2
            rect_y = y_pos - 2

            c.setFillColor(colors.black)
            c.rect(rect_x, rect_y, value_width, 8, fill=1, stroke=0)

            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 7)
            c.drawCentredString(text_x + 2 / 3 * available_width, y_pos, value)
        else:
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 7)
            c.drawCentredString(text_x + 2 / 3 * available_width, y_pos, value)

# ======================================================
# Multi-label PDF sheet
# ======================================================
def generate_sheet_direct(
    df,
    visible_columns,
    qr_column,
    highlight_column,
    label_width,
    label_height,
    qr_size,
    row_height_factor,
    sidebar_factor,
    highlight_padding,
    show_border=True,
    show_column_names=True,
    side_highlight=False,
    qr_left_offset=2,
    page_format="A4",
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
            visible_columns, qr_column, highlight_column,
            label_width, label_height, qr_size,
            row_height_factor, sidebar_factor, highlight_padding,
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
st.subheader("Dataset summary")

c1, c2, c3 = st.columns(3)
c1.metric("Rows", len(df))
c2.metric("Columns", df.shape[1])
c3.metric("Source", st.session_state.data_source)

with st.expander("Column overview"):
    summary_df = pd.DataFrame({
        "Column": df.columns,
        "Type": df.dtypes.astype(str),
        "Non-null": df.notna().sum().values
    })
    st.dataframe(summary_df, use_container_width=True)
    
with st.expander("Dataset controls"):
    st.warning("This will clear the current dataset and return you to the start page.")

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
    default=df.columns.tolist()[:4],
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

# ---- QR options ----
st.sidebar.header("QR code")
enable_qr = st.sidebar.checkbox("Include QR code", True)

if enable_qr:
    qr_column = st.sidebar.selectbox("QR column", df.columns.tolist())
    qr_size = st.sidebar.slider(
        "QR size (mm)", 8, max(8, label_height - 2), min(18, label_height - 2)
    )
    qr_left_offset = st.sidebar.slider("QR left offset (mm)", 0, int(label_width / 2), 2)
else:
    qr_column = None
    qr_size = 0
    qr_left_offset = 0

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
    qr_column,
    highlight_column,
    label_width,
    label_height,
    qr_size,
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
    ["A4", "Letter", "LabelPrinter"]
)

# ---- Generate button ----
if st.button("Generate Multi-Label PDF"):
    pdf_path = generate_sheet_direct(
        df,
        visible_columns,
        qr_column,
        highlight_column,
        label_width,
        label_height,
        qr_size,
        row_height_factor,
        sidebar_factor,
        highlight_padding,
        show_border=show_border,
        show_column_names=show_column_names,
        side_highlight=side_highlight,
        qr_left_offset=qr_left_offset,
        page_format=page_format,  # <- pass selected format
    )
    st.success("PDF generated")
    st.download_button(
        "Download PDF",
        data=open(pdf_path, "rb"),
        file_name=f"multi_labels_{page_format}.pdf",
        mime="application/pdf",
    )