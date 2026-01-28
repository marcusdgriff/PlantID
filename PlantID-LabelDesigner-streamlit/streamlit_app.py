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

    # ---- Outer border ----
    if show_border:
        c.setStrokeColor(colors.lightgrey)
        c.setLineWidth(0.5)
        c.rect(x, y, lw_pt, lh_pt, stroke=1, fill=0)

    # ---- Text rows ----
    row_count = max(len(visible_columns), 1)
    row_height = ((lh_pt - 2 * pad_pt) / row_count) * row_height_factor
    text_y_start = y + lh_pt - pad_pt - row_height * 0.1

    # ---- Side highlight strip (rotated 90°) ----
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

        # Column name
        c.setFillColor(colors.black)
        c.setFont(font_name, font_size)
        c.saveState()
        c.translate(x + side_col_width / 2, sidebar_bottom + name_width / 2)
        c.rotate(90)
        c.drawCentredString(0, 0, f"{col_name}:")
        c.restoreState()

        # Black bar for value
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

    # ---- QR code ----
    if qr_column is not None and qr_size > 0:
        qr_x = x + qr_left_offset * mm
        qr_y = y + (lh_pt - qr_pt) / 2
        qr_value = str(df_row[qr_column])

        qrobj = qr.QrCodeWidget(qr_value)
        bounds = qrobj.getBounds()
        qr_w = bounds[2] - bounds[0]
        qr_h = bounds[3] - bounds[1]
        scale = qr_pt / max(qr_w, qr_h)

        d = Drawing(qr_pt, qr_pt, transform=[scale, 0, 0, scale, 0, 0])
        d.add(qrobj)
        renderPDF.draw(d, c, qr_x, qr_y)

        text_x = qr_x + qr_pt + 4 * mm
    else:
        text_x = x + pad_pt

    available_width = lw_pt - (text_x - x) - pad_pt

    # ---- Text columns ----
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
            rect_height = 8

            c.setFillColor(colors.black)
            c.rect(rect_x, rect_y, value_width, rect_height, fill=1, stroke=0)

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
):

    page_width, page_height = A4
    c = canvas.Canvas("multi_labels.pdf", pagesize=A4)
    margin = 5 * mm

    x = margin
    y = page_height - label_height * mm - margin

    for _, row in df.iterrows():
        draw_label_on_canvas(
            c,
            row,
            x,
            y,
            visible_columns,
            qr_column,
            highlight_column,
            label_width,
            label_height,
            qr_size,
            row_height_factor,
            sidebar_factor,
            highlight_padding,
            padding=4,
            show_border=show_border,
            show_column_names=show_column_names,
            side_highlight=side_highlight,
            qr_left_offset=qr_left_offset,
        )

        x += label_width * mm + margin
        if x + label_width * mm + margin > page_width:
            x = margin
            y -= label_height * mm + margin
            if y - label_height * mm < 0:
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

uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
if not uploaded_file:
    st.info("Upload a CSV to start")
    st.stop()

df = pd.read_csv(uploaded_file)

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
        "QR size (mm)",
        8,
        max(8, label_height - 2),
        min(18, label_height - 2),
    )
    qr_left_offset = st.sidebar.slider(
        "QR left offset (mm)",
        0,
        int(label_width / 2),
        2,
    )
else:
    qr_column = None
    qr_size = 0
    qr_left_offset = 0

# ---- Design ----
st.sidebar.header("Design")
show_column_names = st.sidebar.checkbox("Show column names", True)
row_height_factor = st.sidebar.slider("Row height factor", 0.1, 1.5, 0.9)

highlight_column = st.sidebar.selectbox(
    "Highlight column",
    ["None"] + df.columns.tolist(),
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

try:
    # 1. Generate the single label PDF into memory
    buffer = io.BytesIO()
    c_prev = canvas.Canvas(buffer, pagesize=(label_width * mm, label_height * mm))
    
    draw_label_on_canvas(
        c_prev,
        df.iloc[row_index],
        0,
        0,
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

    # 2. Convert PDF buffer to Image using pypdfium2
    pdf = pdfium.PdfDocument(buffer)
    page = pdf[0]
    # Scale=3 gives roughly 200-220 DPI resolution, nice and crisp
    bitmap = page.render(scale=3) 
    pil_image = bitmap.to_pil()
    
    # 3. Display
    st.image(pil_image, caption=f"Previewing Row {row_index + 1}")

except Exception as e:
    st.error(f"An error occurred during preview: {e}")

# ---- Export ----
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
        show_border,
        show_column_names,
        side_highlight,
        qr_left_offset,
    )
    st.success("PDF generated")
    st.download_button(
        "Download PDF",
        data=open(pdf_path, "rb"),
        file_name="multi_labels.pdf",
        mime="application/pdf",
    )