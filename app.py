import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ✅ ดึงข้อมูลจาก Google Sheets (CSV URL)
def load_sales_data():
    sheet_id = "15_JmzjUIt2LXrUlVug3yGYlZ2XslwVnlt6ge7DIT-rE"
    gid = "949201953"
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"

    # โหลด
    df = pd.read_csv(csv_url)

    # ✅ เปลี่ยนชื่อคอลัมน์ให้ตรง
    df = df.rename(columns={
        'Timestamp': 'timestamp',
        'สาขาที่ต้องการคีย์ข้อมูล': 'branch',
        'ประเภทบัญชี': 'trans_type',
        'รายละเอียด: รายรับ': 'income_cat',
        'จำนวนเงิน (บาท): รายรับ': 'income_thb',
        'รายละเอียด: รายจ่าย': 'expense_cat',
        'จำนวนเงิน (บาท): รายจ่าย': 'expense_thb',
        'ชื่อ Supplier / ลูกค้า': 'cust_name'
    })

    # ✅ ทำความสะอาดเบื้องต้น
    df = df.dropna(subset=['timestamp', 'trans_type'])

    # ✅ สร้างคอลัมน์ description และ amount_thb
    df['description'] = df.apply(
        lambda row: row['expense_cat'] if row['trans_type'] == 'รายจ่าย'
                    else row['income_cat'] if row['trans_type'] == 'รายรับ'
                    else None,
        axis=1
    )

    df['amount_thb'] = df.apply(
        lambda row: row['expense_thb'] if row['trans_type'] == 'รายจ่าย'
                    else row['income_thb'] if row['trans_type'] == 'รายรับ'
                    else None,
        axis=1
    )

    # ✅ ทำความสะอาดจำนวนเงิน
    for col in ['income_thb', 'expense_thb', 'amount_thb']:
        df[col] = (
            df[col]
            .replace('[฿,]', '', regex=True)
            .replace('', '0')
            .pipe(pd.to_numeric, errors='coerce')
            .fillna(0.0)
        )

    # ✅ แปลง timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp'], dayfirst=True, errors='coerce')
    df['cust_name'] = df['cust_name'].replace('-', np.nan)
    df = df[['timestamp', 'branch', 'trans_type', 'cust_name', 'description', 'amount_thb']].dropna(how='all')
    df['year_month'] = df['timestamp'].dt.to_period('M').astype(str)

    # ✅ แยกยอดขายและต้นทุน
    df['ยอดขาย'] = np.where(df['trans_type'] == 'รายรับ', df['amount_thb'], 0)
    df['ต้นทุน'] = np.where(df['trans_type'] == 'รายจ่าย', df['amount_thb'], 0)

    # ✅ รวมกำไร
    sale_df = df.groupby(['year_month', 'branch'])[['ยอดขาย', 'ต้นทุน']].sum()
    sale_df['กำไร'] = sale_df['ยอดขาย'] - sale_df['ต้นทุน']
    return sale_df.reset_index()

# ✅ App setup
app = dash.Dash(__name__)

branches = [
    'ดาเลเซอร์ (รวมทุกสาขา)',
    'A&D จิวเวลรี่ราคาส่ง',
    'ASASA',
    'LaGemme',
    'velan.co'
]

app.layout = html.Div(
    style={'backgroundColor': '#111', 'padding': '20px'},
    children=[
        html.H1(
            "📈 Dashboard",
            style={'color': 'white', 'fontFamily': 'Noto Sans Thai, Arial, sans-serif'}
        ),

        html.Label(
            "เลือกสาขา:",
            style={'color': 'white', 'fontFamily': 'Noto Sans Thai, Arial, sans-serif'}
        ),

        dcc.Dropdown(
            id='branch-filter',
            options=[{'label': b, 'value': b} for b in branches],
            value='ดาเลเซอร์ (รวมทุกสาขา)'
        ),

        html.Div(
            id='summary-container',
            style={
                'display': 'flex',
                'justifyContent': 'space-around',
                'margin': '20px 0',
                'fontSize': '18px',
                'fontWeight': 'bold',
                'fontFamily': 'Noto Sans Thai, Arial, sans-serif',
                'color': 'white'
            }
        ),

        dcc.Graph(id='sales-cost-profit-graph')
    ]
)


# ✅ Callback
@app.callback(
    [Output('sales-cost-profit-graph', 'figure'),
     Output('summary-container', 'children')],
    [Input('branch-filter', 'value')]
)
def update_graph(selected_branch):
    # Load fresh data each time (for always up-to-date)
    df = load_sales_data()

    # Filter by branch
    if selected_branch == 'ดาเลเซอร์ (รวมทุกสาขา)':
        filtered_df = df.copy()
    else:
        filtered_df = df[df['branch'] == selected_branch]

    # Monthly summary
    monthly = filtered_df.groupby(['year_month'])[['ยอดขาย', 'ต้นทุน', 'กำไร']].sum().reset_index()

    # Average profit per month
    if selected_branch == 'ดาเลเซอร์ (รวมทุกสาขา)':
        total_profit_all = df['กำไร'].sum()
        total_months = df['year_month'].nunique()
        avg_sales_per_month = total_profit_all / total_months if total_months != 0 else 0
    else:
        branch_data = df[df['branch'] == selected_branch]
        total_profit_branch = branch_data['กำไร'].sum()
        months_branch = branch_data['year_month'].nunique()
        avg_sales_per_month = total_profit_branch / months_branch if months_branch != 0 else 0

    # Summary numbers
    def fmt(x):
        return f"{x:,.0f}"

    total_sales = monthly['ยอดขาย'].sum()
    total_cost = monthly['ต้นทุน'].sum()
    total_profit = monthly['กำไร'].sum()
    profit_percent = (total_profit / total_sales * 100) if total_sales != 0 else 0

    summary_children = [
        html.Div([html.Div("ยอดขาย"), html.Div(f"{fmt(total_sales)} บาท", style={'color': 'white'})]),
        html.Div([html.Div("ต้นทุน"), html.Div(f"{fmt(total_cost)} บาท", style={'color': 'red'})]),
        html.Div([html.Div("กำไร"), html.Div(f"{fmt(total_profit)} บาท", style={'color': 'green'})]),
        html.Div([html.Div("กำไร (%)"), html.Div(f"{profit_percent:.2f} %", style={'color': 'green'})]),
    ]

    # Graph
    fig = go.Figure()

    fig.add_bar(
        x=monthly['year_month'],
        y=monthly['ต้นทุน'],
        name='ต้นทุน',
        marker_color='red',
        text=monthly['ต้นทุน'],
        textposition='inside',
        texttemplate='%{text:,.0f}'
    )

    fig.add_bar(
        x=monthly['year_month'],
        y=monthly['กำไร'],
        name='กำไร',
        marker_color='green',
        text=monthly['กำไร'],
        textposition='inside',
        texttemplate='%{text:,.0f}'
    )

    fig.add_trace(
        go.Scatter(
            x=monthly['year_month'],
            y=monthly['ยอดขาย'],
            mode='lines+markers+text',
            name='ยอดขาย',
            line=dict(color='white', width=3),
            text=monthly['ยอดขาย'],
            textposition='top center',
            texttemplate='%{text:,.0f}'
        )
    )

    # Average line
    fig.add_hline(
        y=avg_sales_per_month,
        line_dash="dash",
        line_color="yellow",
        annotation_text=f"รายได้เฉลี่ย/เดือน: {fmt(avg_sales_per_month)} บาท",
        annotation_position="top right",
        annotation_font_color="yellow",
    )

    fig.update_layout(
        barmode='relative',
        title=f'สรุปผลดำเนินงานธุรกิจ - {selected_branch}',
        xaxis_title='ปี-เดือน',
        yaxis_title='จำนวนเงิน',
        template='plotly_dark',
        font=dict(family="Noto Sans Thai, Arial, sans-serif", size=14, color="white"),
        legend=dict(title='รายการ', orientation='h', yanchor='bottom', y=1, xanchor='right', x=1),
        margin=dict(t=40, b=80, l=80, r=80),
    )

    return fig, summary_children


# ✅ Run
if __name__ == '__main__':
    app.run()
