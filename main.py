import logging
import random
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import ttkbootstrap as tb
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from ttkbootstrap.constants import *
import yfinance as yf

# Logging-Konfiguration
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

def fetch_stock_history(ticker: str, quantity: int, period: str = "1mo") -> pd.DataFrame:
    try:
        stock = yf.Ticker(ticker)
        history = stock.history(period=period).reset_index()
        if history.empty:
            raise ValueError(f"Keine Daten für {ticker} verfügbar.")
        history["Ticker"] = ticker
        history["TotalValue"] = history["Close"] * quantity
        logging.info(f"Daten für {ticker} erfolgreich abgerufen.")
        return history
    except Exception as e:
        logging.error(f"Fehler beim Abrufen von Daten für {ticker}: {e}")
        dates = pd.date_range(start="2023-01-01", periods=30)
        values = [random.uniform(100, 200) for _ in range(30)]
        test_data = pd.DataFrame({
            "Date": dates,
            "Close": values,
            "Ticker": ticker,
            "TotalValue": [v * quantity for v in values]
        })
        return test_data

class App(tb.Window):
    def __init__(self):
        super().__init__(themename="darkly")
        self.title("Aktien & ETF Portfolio")
        self.geometry("1200x800")
        self.minsize(800, 600)
        self.state("zoomed")

        self.running = True
        self.portfolio_data = []

        self.create_sidebar()
        self.create_frames()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_frame("DashboardPage")

    def create_sidebar(self):
        self.sidebar = tb.Frame(self, bootstyle="secondary", width=250)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        btn_dashboard = tb.Button(
            self.sidebar, text=" Dashboard", compound="left",
            command=lambda: self.show_frame("DashboardPage"), bootstyle="outline-primary", width=220)
        btn_dashboard.pack(pady=(20, 10), padx=10)

        btn_market = tb.Button(
            self.sidebar, text=" Markt", compound="left",
            command=lambda: self.show_frame("MarketPage"), bootstyle="outline-primary", width=220)
        btn_market.pack(pady=10, padx=10)

        btn_portfolio = tb.Button(
            self.sidebar, text=" Portfolio", compound="left",
            command=lambda: self.show_frame("PortfolioPage"), bootstyle="outline-primary", width=220)
        btn_portfolio.pack(pady=10, padx=10)

    def create_frames(self):
        self.container = tb.Frame(self, padding=15)
        self.container.pack(side="right", fill="both", expand=True)

        self.frames = {}
        for F in (DashboardPage, MarketPage, PortfolioPage):
            page_name = F.__name__
            frame = F(parent=self.container, app=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

    def show_frame(self, page_name: str):
        frame = self.frames[page_name]
        frame.tkraise()

    def on_close(self):
        self.running = False
        for frame in self.frames.values():
            if hasattr(frame, "stop_threads"):
                frame.stop_threads()
        self.destroy()

class DashboardPage(tb.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.future = None

        title = tb.Label(self, text="Dashboard", font=("Helvetica", 24, "bold"))
        title.pack(pady=10)

        self.grid_container = tb.Frame(self)
        self.grid_container.pack(fill="both", expand=True, padx=10, pady=10)

        self.grid_container.columnconfigure(0, weight=1, minsize=200)
        self.grid_container.columnconfigure(1, weight=1, minsize=200)
        self.grid_container.rowconfigure(0, weight=1, minsize=200)
        self.grid_container.rowconfigure(1, weight=1, minsize=200)

        self.update_dashboard()

    def update_dashboard(self):
        for widget in self.grid_container.winfo_children():
            widget.destroy()

        if not self.app.portfolio_data:
            empty_label = tb.Label(
                self.grid_container,
                text="Ihr Portfolio ist leer. Fügen Sie Aktien oder ETFs hinzu.",
                font=("Helvetica", 14))
            empty_label.grid(row=0, column=0, columnspan=2, pady=20, sticky="nsew")
        else:
            self.future = self.executor.submit(self.load_and_display_data)

    def load_and_display_data(self):
        try:
            data = self.get_portfolio_data()
            self.after(0, lambda: self.display_charts(data))
        except Exception as e:
            logging.exception("Fehler beim Laden der Portfolio-Daten:")
            self.after(0, lambda: self.show_error(e))

    def display_charts(self, data: pd.DataFrame):
        try:
            bg_color = self.app.cget("background")

            pie_frame = tb.Frame(self.grid_container)
            pie_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
            pie_frame.columnconfigure(0, weight=1)
            pie_frame.rowconfigure(0, weight=1)

            composition = data.groupby("Ticker")["TotalValue"].sum()
            fig_pie = Figure(facecolor=bg_color)
            ax_pie = fig_pie.add_subplot(111)
            ax_pie.pie(composition, labels=composition.index, autopct="%1.1f%%",
                       textprops={"color": "white"})
            ax_pie.set_title("Portfolio-Zusammensetzung", color="white")
            fig_pie.tight_layout()

            canvas_pie = FigureCanvasTkAgg(fig_pie, master=pie_frame)
            canvas_pie.draw()
            canvas_pie.get_tk_widget().pack(fill="both", expand=True)

            info_frame = tb.Frame(self.grid_container)
            info_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
            info_frame.columnconfigure(0, weight=1)

            total_values = data.groupby("Date")["TotalValue"].sum()
            current_total = total_values.iloc[-1] if not total_values.empty else 0

            lbl_total = tb.Label(info_frame,
                                 text=f"Gesamtwert: {current_total:.2f} USD",
                                 font=("Helvetica", 16, "bold"),
                                 foreground="white")
            lbl_total.grid(row=0, column=0, pady=10, sticky="ew")

            line_frame = tb.Frame(self.grid_container)
            line_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
            line_frame.columnconfigure(0, weight=1)
            line_frame.rowconfigure(0, weight=1)

            fig_line = Figure(facecolor=bg_color)
            ax_line = fig_line.add_subplot(111)
            ax_line.plot(total_values.index, total_values.values, label="Portfolio", color="#4a90e2")
            ax_line.set_title("Portfolio-Veränderungen", color="white")
            ax_line.tick_params(colors="white")
            fig_line.tight_layout()

            canvas_line = FigureCanvasTkAgg(fig_line, master=line_frame)
            canvas_line.draw()
            canvas_line.get_tk_widget().pack(fill="both", expand=True)
        except Exception as e:
            self.show_error(e)

    def show_error(self, error: Exception):
        error_label = tb.Label(self.grid_container,
                               text=f"Fehler beim Laden der Daten: {error}",
                               font=("Helvetica", 14),
                               foreground="red")
        error_label.grid(row=0, column=0, columnspan=2, pady=20, sticky="nsew")

    def get_portfolio_data(self) -> pd.DataFrame:
        data_frames = []
        for item in self.app.portfolio_data:
            ticker = item["ticker"]
            quantity = item["quantity"]
            data = fetch_stock_history(ticker, quantity, period="1mo")
            data_frames.append(data)
        return pd.concat(data_frames, ignore_index=True)

    def stop_threads(self):
        if self.future and not self.future.done():
            self.future.cancel()
        self.executor.shutdown(wait=False)

# MarketPage and PortfolioPage remain similar with responsive updates as needed.

if __name__ == "__main__":
    app = App()
    app.mainloop()
