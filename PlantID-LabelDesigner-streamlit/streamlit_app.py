import streamlit as st
import pandas as pd
import io
import os
import json
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
# Session state for dataset
# ======================================================
if "df" not in st.session_state:
    st.session_state.df = None
if "data_source" not in st.session_state:
    st.session_state.data_source = None

TEMPLATE_VERSION = 1
TEMPLATE_DEFAULTS = {
    "units_select": "Metric (mm)",
    "preset_select": "Custom",
    "label_width_mm_slider": 70,
    "label_height_mm_slider": 35,
    "label_width_in_slider": 2.75,
    "label_height_in_slider": 1.37,
    "code_type_select": "QR",
    "code_column_select": None,
    "qr_size_slider": 18,
    "barcode_width_slider": 25,
    "barcode_height_slider": 10,
    "qr_left_offset_slider": 2,
    "show_column_names_check": True,
    "row_height_factor_slider": 0.9,
    "text_left_offset_slider": 0,
    "label_font_select": "Helvetica",
    "label_font_size_slider": 7,
    "highlight_column_select": "None",
    "highlight_padding_slider": 2,
    "side_highlight_check": False,
    "sidebar_factor_slider": 0.1,
    "show_border_check": True,
}


def build_template_payload():
    settings = {
        key: st.session_state.get(key, default)
        for key, default in TEMPLATE_DEFAULTS.items()
    }
    return {
        "template_version": TEMPLATE_VERSION,
        "app": "PlantID Label Designer",
        "settings": settings,
    }


def load_template_payload(uploaded_file):
    if uploaded_file is None:
        return None, "No file selected."
    try:
        raw = uploaded_file.getvalue()
        parsed = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        return None, f"Could not read template file: {exc}"

    if not isinstance(parsed, dict):
        return None, "Template must be a JSON object."

    settings = parsed.get("settings", parsed)
    if not isinstance(settings, dict):
        return None, "Template settings must be a JSON object."

    applied = {}
    for key in TEMPLATE_DEFAULTS:
        if key in settings:
            applied[key] = settings[key]

    if not applied:
        return None, "No supported settings were found in the template."

    for key, value in applied.items():
        st.session_state[key] = value

    return applied, None


def ensure_choice(key, options, default):
    if key not in st.session_state:
        st.session_state[key] = default
    if st.session_state[key] not in options:
        st.session_state[key] = default


def ensure_int_range(key, default, min_value, max_value):
    try:
        value = int(st.session_state.get(key, default))
    except Exception:
        value = default
    st.session_state[key] = max(min_value, min(max_value, value))


def ensure_float_range(key, default, min_value, max_value):
    try:
        value = float(st.session_state.get(key, default))
    except Exception:
        value = default
    st.session_state[key] = max(min_value, min(max_value, value))


def ensure_bool(key, default):
    st.session_state[key] = bool(st.session_state.get(key, default))

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
            
            # Draw directly to canvas
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
    repeat_count=1,
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
        for _ in range(repeat_count):
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
# Start page
# ======================
if st.session_state.df is None:
    st.subheader("Start")

    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    use_template_layout = st.toggle("Use a template layout", value=False, key="use_template_layout_toggle")
    template_file = None

    if use_template_layout:
        template_file = st.file_uploader(
            "Choose template file",
            type=["json"],
            key="start_template_file",
        )
        if st.button("Load template", key="load_template_btn"):
            _, template_error = load_template_payload(template_file)
            if template_error:
                st.error(template_error)
            else:
                st.success(f"Loaded template: {template_file.name}")

    if st.button("Use example dataset"):
        example_path = os.path.join(os.path.dirname(__file__), "PV1_metadata.csv")
        # Create a simple example if file doesn't exist
        if os.path.exists(example_path):
            st.session_state.df = pd.read_csv(example_path)
        else:
            st.session_state.df = pd.DataFrame({
                "ID": ["P001", "P002", "P003", "P004"],
                "Species": ["Arabidopsis", "Arabidopsis", "Wheat", "Maize"],
                "Genotype": ["Col-0", "Ler", "Bobwhite", "B73"],
                "Treatment": ["Control", "Salt", "Control", "Drought"]
            })
        st.session_state.data_source = "Example dataset"
        st.rerun()

    if uploaded_file:
        st.session_state.df = pd.read_csv(uploaded_file)
        st.session_state.data_source = "Uploaded CSV"
        st.rerun()

    st.info("Upload a CSV or use the example dataset to begin.")
    st.stop()

# ==========================================
# Section order containers
# ==========================================
summary_container = st.container()
preview_container = st.container()
filter_container = st.container()
export_container = st.container()

with filter_container:
    # ==========================================
    # 3. Filter & Select Rows
    # ==========================================
    st.subheader("3. Filter & Select Rows")

    st.write("Check the **Print** box for rows you want to include in the PDF:")

    table_col, controls_col = st.columns([4, 1])
    with controls_col:
        filter_col = st.selectbox("Filter in column", ["All Columns"] + st.session_state.df.columns.tolist())
        search_query = st.text_input("Search rows", placeholder="Type to filter...")

    if search_query:
        if filter_col == "All Columns":
            mask = st.session_state.df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)
        else:
            mask = st.session_state.df[filter_col].astype(str).str.contains(search_query, case=False, na=False)
        filtered_df = st.session_state.df[mask].copy()
    else:
        filtered_df = st.session_state.df.copy()

    df_for_selection = filtered_df.copy()
    df_for_selection.insert(0, "Print", True)

    with table_col:
        edited_df = st.data_editor(
            df_for_selection,
            column_config={"Print": st.column_config.CheckboxColumn("Print", default=True)},
            disabled=st.session_state.df.columns,
            use_container_width=True,
            hide_index=True,
            key="editor"
        )

    df_to_use = edited_df[edited_df["Print"] == True].drop(columns=["Print"])

    if df_to_use.empty:
        st.warning("No rows selected for printing. Please filter or check boxes above.")

# ---- Sidebar ----
st.sidebar.title("Label Setup")

# 1. Data Fields Category
with st.sidebar.expander("Data Fields", expanded=True):
    visible_columns = st.multiselect(
        "Columns to display",
        st.session_state.df.columns.tolist(),
        default=st.session_state.df.columns.tolist()[:2] if len(st.session_state.df.columns) > 1 else st.session_state.df.columns.tolist(),
    )

    row_index = st.number_input(
        "Preview row",
        min_value=1,
        max_value=max(1, len(filtered_df)),
        value=1,
    ) - 1
    
    repeat_count = st.number_input(
        "Copies per label",
        min_value=1,
        max_value=100,
        value=1,
        help="How many times each record will be printed."
    )

# 2. Label Size Category
with st.sidebar.expander("Label Size", expanded=False):
    UNIT_MM = "Metric (mm)"
    UNIT_INCH_FRACTIONAL = "Imperial (inches)"
    UNIT_INCH_DECIMAL = "Imperial (inch decimal)"

    unit_options = [UNIT_MM, UNIT_INCH_FRACTIONAL, UNIT_INCH_DECIMAL]
    ensure_choice("units_select", unit_options, TEMPLATE_DEFAULTS["units_select"])
    units = st.selectbox("Units", unit_options, key="units_select")

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
        if frac.numerator == 0: return str(whole)
        if whole == 0: return f"{frac.numerator}/{frac.denominator}"
        return f"{whole} {frac.numerator}/{frac.denominator}"

    def format_preset_label(name, display_w_mm, display_h_mm, units_mode):
        if units_mode == UNIT_MM: return f"{name} ({display_w_mm} × {display_h_mm} mm)"
        w_in, h_in = display_w_mm / 25.4, display_h_mm / 25.4
        if units_mode == UNIT_INCH_FRACTIONAL: return f"{name} ({format_fractional_inches(w_in)} × {format_fractional_inches(h_in)} inches)"
        return f"{name} ({w_in:.3f} × {h_in:.3f} inches)"

    preset_options = ["Custom"] + [format_preset_label(n, w, h, units) for n, w, h, _, _ in LABEL_PRESETS]
    ensure_choice("preset_select", preset_options, TEMPLATE_DEFAULTS["preset_select"])
    preset = st.selectbox("Preset", preset_options, key="preset_select")
    
    if preset == "Custom":
        if units == UNIT_MM:
            ensure_int_range("label_width_mm_slider", TEMPLATE_DEFAULTS["label_width_mm_slider"], 10, 140)
            ensure_int_range("label_height_mm_slider", TEMPLATE_DEFAULTS["label_height_mm_slider"], 10, 140)
            label_width = st.slider("Width (mm)", 10, 140, step=1, key="label_width_mm_slider")
            label_height = st.slider("Height (mm)", 10, 140, step=1, key="label_height_mm_slider")
        else:
            step_in = 1 / 16 if units == UNIT_INCH_FRACTIONAL else 0.01
            ensure_float_range("label_width_in_slider", TEMPLATE_DEFAULTS["label_width_in_slider"], 0.4, 5.5)
            ensure_float_range("label_height_in_slider", TEMPLATE_DEFAULTS["label_height_in_slider"], 0.4, 5.5)
            label_width_in = st.slider("Width (in)", 0.4, 5.5, step=step_in, key="label_width_in_slider")
            label_height_in = st.slider("Height (in)", 0.4, 5.5, step=step_in, key="label_height_in_slider")
            label_width, label_height = label_width_in * 25.4, label_height_in * 25.4
    else:
        label_width, label_height = LABEL_PRESETS[preset_options.index(preset)-1][3:5]

# 3. Code Settings Category
with st.sidebar.expander("Code Settings", expanded=False):
    code_type_options = ["QR", "Barcode", "None"]
    ensure_choice("code_type_select", code_type_options, TEMPLATE_DEFAULTS["code_type_select"])
    code_type = st.selectbox("Code type", code_type_options, key="code_type_select")
    if code_type != "None":
        code_column_options = st.session_state.df.columns.tolist()
        ensure_choice("code_column_select", code_column_options, code_column_options[0])
        code_column = st.selectbox("Code column", code_column_options, key="code_column_select")
    else:
        code_column = None

    if code_type == "QR":
        qr_max = max(8, int(label_height - 2))
        ensure_int_range("qr_size_slider", min(18, qr_max), 8, qr_max)
        qr_size = st.slider("QR size (mm)", 8, qr_max, key="qr_size_slider")
        barcode_width = barcode_height = 0
    elif code_type == "Barcode":
        max_barcode_width = max(15, int(label_width - 5))
        max_barcode_height = max(5, int(label_height - 5))
        ensure_int_range("barcode_width_slider", TEMPLATE_DEFAULTS["barcode_width_slider"], 15, max_barcode_width)
        ensure_int_range("barcode_height_slider", TEMPLATE_DEFAULTS["barcode_height_slider"], 5, max_barcode_height)
        barcode_width = st.slider("Barcode width (mm)", 15, max_barcode_width, key="barcode_width_slider")
        barcode_height = st.slider("Barcode height (mm)", 5, max_barcode_height, key="barcode_height_slider")
        qr_size = 0
    else:
        qr_size = barcode_width = barcode_height = 0

    max_qr_left_offset = int(label_width / 2)
    ensure_int_range("qr_left_offset_slider", TEMPLATE_DEFAULTS["qr_left_offset_slider"], 0, max_qr_left_offset)
    qr_left_offset = st.slider("Code left offset (mm)", 0, max_qr_left_offset, key="qr_left_offset_slider")

# 4. Design and Aesthetics Category
with st.sidebar.expander("Design & Aesthetics", expanded=False):
    ensure_bool("show_column_names_check", TEMPLATE_DEFAULTS["show_column_names_check"])
    show_column_names = st.checkbox("Show column names", key="show_column_names_check")
    ensure_float_range("row_height_factor_slider", TEMPLATE_DEFAULTS["row_height_factor_slider"], 0.1, 1.5)
    row_height_factor = st.slider("Row height factor", 0.1, 1.5, key="row_height_factor_slider")
    max_text_left_offset = int(label_width / 2)
    ensure_int_range("text_left_offset_slider", TEMPLATE_DEFAULTS["text_left_offset_slider"], 0, max_text_left_offset)
    text_left_offset = st.slider("Text left offset (mm)", 0, max_text_left_offset, key="text_left_offset_slider")
    label_font_options = ["Helvetica", "Times-Roman", "Courier"]
    ensure_choice("label_font_select", label_font_options, TEMPLATE_DEFAULTS["label_font_select"])
    label_font = st.selectbox("Label font", label_font_options, key="label_font_select")
    ensure_int_range("label_font_size_slider", TEMPLATE_DEFAULTS["label_font_size_slider"], 4, 14)
    label_font_size = st.slider("Label font size (pt)", 4, 14, key="label_font_size_slider")
    highlight_options = ["None"] + st.session_state.df.columns.tolist()
    ensure_choice("highlight_column_select", highlight_options, TEMPLATE_DEFAULTS["highlight_column_select"])
    highlight_column = st.selectbox("Highlight column", highlight_options, key="highlight_column_select")
    highlight_column = None if highlight_column == "None" else highlight_column

    if highlight_column:
        ensure_int_range("highlight_padding_slider", TEMPLATE_DEFAULTS["highlight_padding_slider"], 0, 20)
        ensure_bool("side_highlight_check", TEMPLATE_DEFAULTS["side_highlight_check"])
        highlight_padding = st.slider("Highlight padding", 0, 20, key="highlight_padding_slider")
        side_highlight = st.checkbox("Side strip highlight", key="side_highlight_check")
    else:
        highlight_padding = side_highlight = 0

    if side_highlight:
        ensure_float_range("sidebar_factor_slider", TEMPLATE_DEFAULTS["sidebar_factor_slider"], 0.05, 0.5)
        sidebar_factor = st.slider("Sidebar width factor", 0.05, 0.5, key="sidebar_factor_slider")
    else:
        sidebar_factor = 0
    ensure_bool("show_border_check", TEMPLATE_DEFAULTS["show_border_check"])
    show_border = st.checkbox("Show border", key="show_border_check")

    template_json = json.dumps(build_template_payload(), indent=2).encode("utf-8")
    st.download_button(
        "Save template",
        data=template_json,
        file_name="plantid_label_template.json",
        mime="application/json",
    )

with summary_container:
    # ==========================================
    # 1. Dataset Summary
    # ==========================================
    st.subheader("1. Dataset Summary")
    c1, c2, c3 = st.columns(3)
    c1.metric("Original Rows", len(st.session_state.df))
    c2.metric("Filtered Rows", len(filtered_df))
    c3.metric("Data Source", st.session_state.data_source)

    with st.expander("Dataframe controls"):
        st.warning("This will clear the current dataframe and return you to the start page.")
        if st.button("Clear dataframe and restart"):
            st.session_state.df = None
            st.session_state.data_source = None
            st.rerun()

with preview_container:
    # ==========================================
    # 2. Live Preview
    # ==========================================
    st.subheader("2. Live Preview")
    if not filtered_df.empty:
        buffer = io.BytesIO()
        c_prev = canvas.Canvas(buffer, pagesize=(label_width * mm, label_height * mm))

        draw_label_on_canvas(
            c_prev, filtered_df.iloc[row_index], 0, 0,
            visible_columns, code_column, code_type, highlight_column,
            label_font, label_font_size, label_width, label_height,
            qr_size, barcode_width, barcode_height, row_height_factor,
            sidebar_factor, highlight_padding, show_border=show_border,
            show_column_names=show_column_names, side_highlight=side_highlight,
            qr_left_offset=qr_left_offset, text_left_offset=text_left_offset
        )
        c_prev.save()
        buffer.seek(0)
        st.image(pdfium.PdfDocument(buffer)[0].render(scale=3).to_pil(), caption=f"Previewing Row {row_index + 1}")
    else:
        st.info("No rows match the filter for preview.")

with export_container:
    # ==========================================
    # 4. Export Labels / PDF
    # ==========================================
    st.subheader("4. Export Labels / PDF")
    page_format = st.selectbox("Page size / printer", ["A4", "Letter", "LabelPrinter"], index=2)

    if st.button("Generate Multi-Label PDF"):
        if df_to_use.empty:
            st.error("Cannot generate PDF: No rows selected.")
        else:
            pdf_path = generate_sheet_direct(
                df_to_use, visible_columns, code_column, code_type, highlight_column,
                label_font, label_font_size, label_width, label_height, qr_size,
                barcode_width, barcode_height, row_height_factor, sidebar_factor,
                highlight_padding, show_border, show_column_names, side_highlight,
                qr_left_offset, text_left_offset, page_format, repeat_count
            )
            st.success(f"PDF generated for {len(df_to_use)} unique records ({len(df_to_use)*repeat_count} total labels).")
            st.download_button(
                "Download PDF",
                data=open(pdf_path, "rb"),
                file_name=f"multi_labels_{page_format}.pdf",
                mime="application/pdf"
            )
