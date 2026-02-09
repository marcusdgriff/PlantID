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
    label_font="Helvetica",
    label_font_size=7,
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
    text_left_offset=0,
):
    def font_variant(base_font, variant):
        variants = {
            "Helvetica": {
                "regular": "Helvetica",
                "bold": "Helvetica-Bold",
                "italic": "Helvetica-Oblique",
                "bold_italic": "Helvetica-BoldOblique",
            },
            "Times-Roman": {
                "regular": "Times-Roman",
                "bold": "Times-Bold",
                "italic": "Times-Italic",
                "bold_italic": "Times-BoldItalic",
            },
            "Courier": {
                "regular": "Courier",
                "bold": "Courier-Bold",
                "italic": "Courier-Oblique",
                "bold_italic": "Courier-BoldOblique",
            },
        }
        return variants.get(base_font, variants["Helvetica"]).get(variant, base_font)

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
        font_size = label_font_size

        # Calculate sidebar geometry
        val_w = stringWidth(value, font_variant(label_font, "bold"), font_size) + highlight_padding
        nam_w = stringWidth(f"{col_name}:", font_variant(label_font, "italic"), font_size)
        gap = 1 * mm
        total_h = nam_w + gap + val_w
        sidebar_bottom = y + (lh_pt - total_h) / 2

        # Draw Side Label text
        c.saveState()
        c.setFillColor(colors.black)
        c.setFont(font_variant(label_font, "italic"), font_size)
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
        c.setFont(font_variant(label_font, "bold"), font_size)
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

    text_x += (text_left_offset * mm)

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
            c.setFont(font_variant(label_font, "italic"), label_font_size)
            c.setFillColor(colors.black)
            c.drawRightString(text_x + avail_w * 0.35, y_pos, f"{col_name}:")

        if col_name == highlight_column:
            c.setFont(font_variant(label_font, "bold"), label_font_size)
            v_w = stringWidth(val, font_variant(label_font, "bold"), label_font_size) + highlight_padding
            c.setFillColor(colors.black)
            highlight_height = max(6, label_font_size + 2)
            highlight_y = y_pos - (label_font_size * 0.3)
            c.rect(text_x + avail_w * 0.4 - 2, highlight_y, v_w, highlight_height, fill=1)
            c.setFillColor(colors.white)
            c.drawString(text_x + avail_w * 0.4, y_pos, val)
        else:
            c.setFont(font_variant(label_font, "regular"), label_font_size)
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
    label_font,
    label_font_size,
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
    text_left_offset=0,
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
            label_font,
            label_font_size,
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
            text_left_offset=text_left_offset,
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

UNIT_MM = "Metric (mm)"
UNIT_INCH_FRACTIONAL = "Imperial (inches)"
UNIT_INCH_DECIMAL = "Imperial (inch decimal)"

units = st.sidebar.selectbox(
    "Units",
    [UNIT_MM, UNIT_INCH_FRACTIONAL, UNIT_INCH_DECIMAL],
    index=0,
)

LABEL_PRESETS = [
    ("Cryovial", 25, 12, 25, 12),
    ("Small Label", 25, 67, 67, 25),
    ("Wristband Label", 25, 254, 254, 25),
    ("Small Plant Tag", 50, 25, 50, 25),
    ("Cryobox / Tube", 30, 15, 30, 15),
    ("General Purpose", 76, 25, 76, 25),
    ("Food Label", 76, 51, 76, 51),
    ("Tag Label", 57, 102, 57, 102),
    ("Standard Plant Label", 70, 35, 70, 35),
    ("Large Field Label", 90, 45, 90, 45),
    ("Shipping Label", 102, 152, 102, 152),
    ("Square Label", 51, 51, 51, 51),
]

def format_fractional_inches(value_in):
    from fractions import Fraction
    whole = int(value_in)
    frac = Fraction(value_in - whole).limit_denominator(16)
    if frac.numerator == 0:
        return str(whole)
    if whole == 0:
        return f"{frac.numerator}/{frac.denominator}"
    return f"{whole} {frac.numerator}/{frac.denominator}"

def format_preset_label(name, display_w_mm, display_h_mm, units_mode):
    if units_mode == UNIT_MM:
        return f"{name} ({display_w_mm} × {display_h_mm} mm)"

    w_in = display_w_mm / 25.4
    h_in = display_h_mm / 25.4
    if units_mode == UNIT_INCH_FRACTIONAL:
        return f"{name} ({format_fractional_inches(w_in)} × {format_fractional_inches(h_in)} inches)"
    return f"{name} ({w_in:.3f} × {h_in:.3f} inches)"

preset_options = ["Custom"] + [
    format_preset_label(name, display_w_mm, display_h_mm, units)
    for name, display_w_mm, display_h_mm, _, _ in LABEL_PRESETS
]

preset = st.sidebar.selectbox("Preset", preset_options)
if preset == "Custom":
    if units == UNIT_MM:
        label_width = st.sidebar.slider("Width (mm)", 10, 140, 70, step=1)
        label_height = st.sidebar.slider("Height (mm)", 10, 140, 35, step=1)
    else:
        min_in = 10 / 25.4
        max_in = 140 / 25.4
        step_in = 1 / 16 if units == UNIT_INCH_FRACTIONAL else 0.01
        default_w_in = 70 / 25.4
        default_h_in = 35 / 25.4
        label_width_in = st.sidebar.slider("Width (in)", min_in, max_in, default_w_in, step=step_in)
        label_height_in = st.sidebar.slider("Height (in)", min_in, max_in, default_h_in, step=step_in)
        label_width = label_width_in * 25.4
        label_height = label_height_in * 25.4
else:
    preset_index = preset_options.index(preset) - 1
    _, _, _, label_width, label_height = LABEL_PRESETS[preset_index]

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
    qr_max = max(8, int(label_height - 2))
    qr_default = min(18, qr_max)
    qr_size = st.sidebar.slider(
        "QR size (mm)",
        8,
        qr_max,
        qr_default,
    )
    barcode_width = 0
    barcode_height = 0

elif code_type == "Barcode":
    barcode_width_max = max(15, int(label_width - 5))
    barcode_height_max = max(5, int(label_height - 5))
    barcode_width_default = min(25, barcode_width_max)
    barcode_height_default = min(10, barcode_height_max)
    barcode_width = st.sidebar.slider(
        "Barcode width (mm)", 15, barcode_width_max, barcode_width_default
    )
    barcode_height = st.sidebar.slider(
        "Barcode height (mm)", 5, barcode_height_max, barcode_height_default
    )
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
text_left_offset = st.sidebar.slider("Text left offset (mm)", 0, int(label_width / 2), 0)

label_font = st.sidebar.selectbox(
    "Label font",
    ["Helvetica", "Times-Roman", "Courier"],
    index=0,
)
label_font_size = st.sidebar.slider("Label font size (pt)", 4, 14, 7)

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
    label_font,
    label_font_size,
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
    text_left_offset=text_left_offset,
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
        label_font,
        label_font_size,
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
        text_left_offset=text_left_offset,
        page_format=page_format,
    )
    st.success("PDF generated")
    st.download_button(
        "Download PDF",
        data=open(pdf_path, "rb"),
        file_name=f"multi_labels_{page_format}.pdf",
        mime="application/pdf",
    )
