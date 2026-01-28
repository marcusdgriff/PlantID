import streamlit as st
import pandas as pd
import io
from reportlab.lib.pagesizes import mm, A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.graphics.barcode import qr
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing
from pdf2image import convert_from_bytes
from reportlab.pdfbase.pdfmetrics import stringWidth

# ======================
# Draw a single label directly onto a canvas
# ======================
def draw_label_on_canvas(c, df_row, x, y,
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
                         qr_left_offset=2
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

    # ---- Text rows setup ----
    row_count = max(len(visible_columns), 1)
    row_height = ((lh_pt - 2*pad_pt) / row_count) * row_height_factor
    text_y_start = y + lh_pt - pad_pt - row_height*0.1

    # ---- Side highlight strip (rotated 90°) ----
    side_col_width = 0
    if side_highlight and highlight_column:
        side_col_width = lw_pt * sidebar_factor

        col_name = highlight_column
        value = str(df_row[highlight_column])

        font_size = 6
        font_value = "Helvetica-Bold"
        font_name = "Helvetica-Oblique"

        # Measure widths (rotated = vertical length)
        value_width = stringWidth(value, font_value, font_size) + highlight_padding
        name_width = stringWidth(f"{col_name}:", font_name, font_size)
        gap = 1 * mm  # gap between name and value

        # Total height of sidebar (name + gap + value)
        total_height = name_width + gap + value_width

        # Sidebar bottom (vertically center the whole strip)
        sidebar_bottom = y + (lh_pt - total_height)/2

        # ---- Draw column name first (bottom row after rotation) ----
        name_center_y = sidebar_bottom + name_width/2
        c.setFillColor(colors.black)
        c.setFont(font_name, font_size)
        c.saveState()
        c.translate(x + side_col_width/2, name_center_y)
        c.rotate(90)
        c.drawCentredString(0, 0, f"{col_name}:")
        c.restoreState()

        # ---- Draw black bar behind value (top row after rotation) ----
        value_rect_y = sidebar_bottom + name_width + gap
        value_rect_x = x
        c.setFillColor(colors.black)
        c.rect(value_rect_x, value_rect_y, side_col_width, value_width, fill=1, stroke=0)

        # Draw value text centered inside black bar
        c.setFillColor(colors.white)
        c.setFont(font_value, font_size)
        c.saveState()
        c.translate(x + side_col_width/2, value_rect_y + value_width/2)
        c.rotate(90)
        c.drawCentredString(0, 0, value)
        c.restoreState()

    # ---- QR code ----
    qr_x = x + qr_left_offset * mm
    qr_y = y + (lh_pt - qr_pt) / 2
    qr_value = str(df_row[qr_column])
    qrobj = qr.QrCodeWidget(qr_value)
    bounds = qrobj.getBounds()
    qr_w = bounds[2] - bounds[0]
    qr_h = bounds[3] - bounds[1]
    scale = qr_pt / max(qr_w, qr_h)
    d = Drawing(qr_pt, qr_pt, transform=[scale,0,0,scale,0,0])
    d.add(qrobj)
    renderPDF.draw(d, c, qr_x, qr_y)

    # ---- Text columns ----
    text_x = qr_x + qr_pt + 4*mm
    available_width = lw_pt - (text_x - x) - pad_pt

    for idx, col_name in enumerate(visible_columns):
        value = str(df_row[col_name])
        y_pos = text_y_start - idx * row_height

        # Column label
        if show_column_names:
            c.setFont("Helvetica-Oblique", 7)
            c.setFillColor(colors.black)
            c.drawRightString(text_x + available_width/3, y_pos, col_name + ":")

        # Column value with auto-fit highlight
        if col_name == highlight_column:
            c.setFont("Helvetica-Bold", 7)
            c.setFillColor(colors.black)

            # Auto-adjust width of black background based on text
            value_width = stringWidth(value, "Helvetica-Bold", 7) + highlight_padding
            rect_x = text_x + 2/3 * available_width - value_width/2
            rect_y = y_pos - 2
            rect_height = 8
            c.setFillColor(colors.black)
            c.rect(rect_x, rect_y, value_width, rect_height, fill=1, stroke=0)

            # Draw the value text
            c.setFillColor(colors.white)
            c.drawCentredString(text_x + 2/3 * available_width, y_pos, value)
        else:
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 7)
            c.drawCentredString(text_x + 2/3 * available_width, y_pos, value)

# ======================
# Multi-label PDF sheet generation
# ======================
def generate_sheet_direct(df, visible_columns, qr_column, highlight_column,
                          label_width, label_height, qr_size, row_height_factor,
                          sidebar_factor, highlight_padding,
                          show_border=True,
                          show_column_names=True,
                          side_highlight=False,
                          qr_left_offset=2
                          ):

    page_width, page_height = A4
    c = canvas.Canvas("multi_labels.pdf", pagesize=A4)
    margin = 5 * mm
    x, y = margin, page_height - label_height*mm - margin

    for idx, row in df.iterrows():
        draw_label_on_canvas(
            c,
            row,
            x, y,
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
            qr_left_offset=qr_left_offset
        )
        x += label_width*mm + margin
        if x + label_width*mm + margin > page_width:
            x = margin
            y -= label_height*mm + margin
            if y - label_height*mm < 0:
                c.showPage()
                x, y = margin, page_height - label_height*mm - margin

    c.save()
    return "multi_labels.pdf"

# ======================
# Streamlit interface
# ======================
st.set_page_config(layout="wide")
st.title("PlantID Label Designer")

# ---- Load CSV ----
uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
if uploaded_file:
    df = pd.read_csv(uploaded_file)
else:
    st.info("Upload a CSV to start")
    st.stop()

# ---- Sidebar config ----
st.sidebar.title("Label Setup")

# ======================
# Data field selection
# ======================
st.sidebar.header("Data fields")

visible_columns = st.sidebar.multiselect(
    "Columns to display on label",
    df.columns.tolist(),
    default=df.columns.tolist()[:4]
)

qr_column = st.sidebar.selectbox(
    "QR code column",
    df.columns.tolist()
)

row_index_ui = st.sidebar.number_input(
    "Preview row index",
    min_value=1,
    max_value=len(df),
    value=1,
    step=1
)

# Convert to 0-based index for pandas
row_index = row_index_ui - 1

# ======================
# Label size setup
# ======================
st.sidebar.header("Label size")

# ======================
# Common label size presets (mm)
# ======================
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


preset_name = st.sidebar.selectbox(
    "Label size preset",
    list(LABEL_PRESETS.keys()),
    index=list(LABEL_PRESETS.keys()).index("Standard Plant Label (70 × 35 mm / 2.76 × 1.38)")
)

if preset_name != "Custom":
    label_width, label_height = LABEL_PRESETS[preset_name]
    st.sidebar.caption(f"Preset size: {label_width} × {label_height} mm")
else:
    # Both typed input and slider for custom size
    col1, col2 = st.sidebar.columns(2)
    label_width = col1.number_input("Label width (mm)", 5, 140, 70)
    label_height = col2.number_input("Label height (mm)", 5, 140, 35)

    # Slider (optional) mirrors number inputs
    label_width = st.sidebar.slider("Label width slider (mm)", 5, 140, label_width)
    label_height = st.sidebar.slider("Label height slider (mm)", 5, 140, label_height)


# ======================
# QR code options
# ======================
st.sidebar.header("QR code")
enable_qr = st.sidebar.checkbox("Include QR code?", value=True)

if enable_qr:
    qr_column = st.sidebar.selectbox(
        "QR code column",
        df.columns.tolist(),
        key="qr_column_select"
    )

    max_qr_size = max(8, label_height - 2)
    default_qr_size = min(18, max_qr_size)

    if 8 >= max_qr_size:
        qr_size = st.sidebar.number_input(
            "QR code size (mm)",
            min_value=8,
            max_value=max_qr_size,
            value=max_qr_size
        )
    else:
        qr_size = st.sidebar.slider(
            "QR code size (mm)",
            8,
            max_qr_size,
            default_qr_size
        )

    qr_left_offset = st.sidebar.slider(
    "QR left offset (mm)",
    min_value=0,
    max_value=int(label_width/2),  # can't exceed half the label width
    value=2,
    step=1
)

else:
    qr_column = None
    qr_size = 0


# ======================
# Label design parameters
# ======================
st.sidebar.header("Label design")

show_column_names = st.sidebar.checkbox(
    "Show column names",
    True
)

row_height_factor = st.sidebar.slider(
    "Row height factor",
    0.1, 1.5, 0.9, 0.05
)

# ---- Highlight column selection ----
highlight_column = st.sidebar.selectbox(
    "Highlight column (optional)",
    ["None"] + df.columns.tolist()
)
highlight_column = None if highlight_column == "None" else highlight_column

# ---- Highlight-dependent options ----
if highlight_column is not None:
    highlight_padding = st.sidebar.slider(
        "Highlight value padding",
        0, 20, 2, 1
    )

    side_highlight = st.sidebar.checkbox(
        "Show highlighted column as side strip",
        False
    )
else:
    highlight_padding = 0
    side_highlight = False

# ---- Side-strip–dependent option ----
if side_highlight:
    sidebar_factor = st.sidebar.slider(
        "Sidebar size factor",
        0.05, 0.5, 0.1, 0.01
    )
else:
    sidebar_factor = 0.0

show_border = st.sidebar.checkbox(
    "Show label border",
    True
)

# ======================
# Print / export parameters
# ======================
st.sidebar.header("Print & export")

st.sidebar.caption(
    "Preview is rasterized for speed.\n"
    "Final PDF preserves vector text and typography."
)

# ---- Live preview ----
buffer = io.BytesIO()
c_preview = canvas.Canvas(buffer, pagesize=(label_width*mm, label_height*mm))
draw_label_on_canvas(
    c_preview,
    df.iloc[row_index],
    x=0,
    y=0,
    visible_columns=visible_columns,
    qr_column=qr_column,
    highlight_column=highlight_column,
    label_width=label_width,
    label_height=label_height,
    qr_size=qr_size,
    row_height_factor=row_height_factor,
    sidebar_factor=sidebar_factor,
    highlight_padding=highlight_padding,
    padding=4,
    show_border=show_border,
    show_column_names=show_column_names,
    side_highlight=side_highlight,
    qr_left_offset=qr_left_offset
)
c_preview.save()
buffer.seek(0)

images = convert_from_bytes(buffer.getvalue(), dpi=300)
st.subheader("Live Preview")
st.image(images[0], use_column_width=False)

# ---- Generate multi-label PDF sheet ----
if st.button("Generate Multi-Label PDF Sheet"):
    output_file = generate_sheet_direct(
        df, visible_columns, qr_column, highlight_column,
        label_width, label_height, qr_size, row_height_factor, sidebar_factor,
        highlight_padding,
        show_border=show_border,
        show_column_names=show_column_names,
        side_highlight=side_highlight,
         qr_left_offset=qr_left_offset
    )
    st.success("Multi-label PDF sheet generated!")
    st.download_button("Download PDF Sheet",
                       data=open(output_file, "rb"),
                       file_name="multi_labels.pdf",
                       mime="application/pdf")