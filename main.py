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
    """
    Holt den historischen Aktienkurs eines Tickers mit yfinance und berechnet den
    Gesamtwert (TotalValue) basierend auf der angegebenen Menge. Bei Fehlern
    werden Dummy-Daten zurückgegeben.
    """
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
        # Erstelle Dummy-Daten als Fallback
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
    """
    Hauptanwendung als ttkbootstrap-Fenster.
    """

    def __init__(self):
        super().__init__(themename="darkly")
        self.title("Aktien & ETF Portfolio")
        self.geometry("1200x800")
        self.state("zoomed")

        # Flag zur sauberen Beendigung von Hintergrundthreads
        self.running = True

        # Zentrales Portfolio: Hier werden alle Einträge gespeichert
        self.portfolio_data = []

        # Sidebar und Hauptcontainer anlegen
        self.create_sidebar()
        self.create_frames()

        # Schließen-Handler setzen
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Mit Dashboard starten
        self.show_frame("DashboardPage")

    def create_sidebar(self):
        """
        Erzeugt die linke Navigations-Sidebar.
        """
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
        """
        Erstellt und verwaltet die verschiedenen Seiten (Frames).
        """
        self.container = tb.Frame(self, padding=15)
        self.container.pack(side="right", fill="both", expand=True)

        self.frames = {}
        for F in (DashboardPage, MarketPage, PortfolioPage):
            page_name = F.__name__
            frame = F(parent=self.container, app=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

    def show_frame(self, page_name: str):
        """
        Hebt den Frame mit dem gegebenen Namen in den Vordergrund.
        """
        frame = self.frames[page_name]
        frame.tkraise()

    def on_close(self):
        """
        Beendet alle laufenden Threads und schließt die Anwendung.
        """
        self.running = False
        for frame in self.frames.values():
            if hasattr(frame, "stop_threads"):
                frame.stop_threads()
        self.destroy()


class DashboardPage(tb.Frame):
    """
    Zeigt das Dashboard, das die Portfolio-Zusammensetzung, die Tagesveränderung
    und die Entwicklung des Portfoliowerts in einem 2×2-Layout darstellt.

    - Obere linke Zelle: Kreisdiagramm (Portfolio-Zusammensetzung)
    - Obere rechte Zelle: Kennzahlen (z. B. Tagesveränderung, % Tagesveränderung,
      Gesamtwert, Gesamtrendite, Top und Flop Performer)
    - Untere Zeile (über beide Spalten): Liniendiagramm (Portfolio-Verlauf)
    """

    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.future = None

        title = tb.Label(self, text="Dashboard", font=("Helvetica", 24, "bold"))
        title.pack(pady=10)

        # Container für das 2×2-Layout (als Grid)
        self.grid_container = tb.Frame(self)
        self.grid_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Konfiguration des Grids: 2 Spalten, 2 Zeilen
        self.grid_container.columnconfigure(0, weight=1)
        self.grid_container.columnconfigure(1, weight=1)
        self.grid_container.rowconfigure(0, weight=1)
        self.grid_container.rowconfigure(1, weight=1)

        self.update_dashboard()

    def update_dashboard(self):
        """
        Startet den asynchronen Abruf der Portfolio-Daten und aktualisiert die
        Diagramme.
        """
        # Container leeren
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
        """
        Lädt die Portfolio-Daten synchron aus yfinance (mit Fallback) und
        aktualisiert anschließend die GUI.
        """
        try:
            data = self.get_portfolio_data()
            self.after(0, lambda: self.display_charts(data))
        except Exception as e:
            logging.exception("Fehler beim Laden der Portfolio-Daten:")
            self.after(0, lambda: self.show_error(e))

    def display_charts(self, data: pd.DataFrame):
        """
        Zeichnet die Diagramme in einem 2×2-Layout:
          - Obere linke Zelle: Kreisdiagramm
          - Obere rechte Zelle: Kennzahlen (Tagesveränderung, % Tagesveränderung,
            Gesamtwert, Gesamtrendite, Top/Flop Performer)
          - Untere Zeile (über beide Spalten): Liniendiagramm
        Dabei wird der Diagrammhintergrund an die Standardfarbe der Anwendung angepasst
        und alle Texte in weiß dargestellt.
        """
        try:
            bg_color = self.app.cget("background")

            # --- Obere linke Zelle: Kreisdiagramm ---
            pie_frame = tb.Frame(self.grid_container)
            pie_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
            pie_frame.columnconfigure(0, weight=1)
            pie_frame.rowconfigure(0, weight=1)

            composition = data.groupby("Ticker")["TotalValue"].sum()
            if composition.empty:
                raise ValueError("Keine gültigen Daten für das Kreisdiagramm verfügbar.")

            fig_pie = Figure(facecolor=bg_color)
            ax_pie = fig_pie.add_subplot(111)
            ax_pie.pie(composition, labels=composition.index, autopct="%1.1f%%",
                       textprops={"color": "white"})
            ax_pie.set_title("Portfolio-Zusammensetzung", color="white")
            fig_pie.tight_layout()

            canvas_pie = FigureCanvasTkAgg(fig_pie, master=pie_frame)
            canvas_pie.draw()
            canvas_pie.get_tk_widget().pack(fill="both", expand=True)

            # --- Obere rechte Zelle: Kennzahlen ---
            info_frame = tb.Frame(self.grid_container)
            info_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
            info_frame.columnconfigure(0, weight=1)

            total_values = data.groupby("Date")["TotalValue"].sum()

            daily_change = total_values.diff().iloc[-1] if len(total_values) >= 2 else 0
            daily_percent = ((total_values.iloc[-1] / total_values.iloc[-2]) - 1) * 100 if len(total_values) >= 2 and \
                                                                                           total_values.iloc[
                                                                                               -2] != 0 else 0
            current_total = total_values.iloc[-1]
            overall_return = ((total_values.iloc[-1] / total_values.iloc[0]) - 1) * 100 if len(total_values) >= 2 and \
                                                                                           total_values.iloc[
                                                                                               0] != 0 else 0

            perf_dict = {}
            for ticker, group in data.groupby("Ticker"):
                group_sorted = group.sort_values("Date")
                start_val = group_sorted["TotalValue"].iloc[0]
                end_val = group_sorted["TotalValue"].iloc[-1]
                pct = ((end_val / start_val) - 1) * 100 if start_val != 0 else 0
                perf_dict[ticker] = pct

            if perf_dict:
                top_ticker = max(perf_dict, key=perf_dict.get)
                top_pct = perf_dict[top_ticker]
                flop_ticker = min(perf_dict, key=perf_dict.get)
                flop_pct = perf_dict[flop_ticker]
            else:
                top_ticker, top_pct, flop_ticker, flop_pct = "n/a", 0, "n/a", 0

            lbl_daily_abs = tb.Label(info_frame,
                                     text=f"Tagesveränderung: {daily_change:.2f} USD",
                                     font=("Helvetica", 16, "bold"),
                                     foreground="green" if daily_change >= 0 else "red")
            lbl_daily_abs.grid(row=0, column=0, pady=(10, 5), sticky="ew")

            lbl_daily_pct = tb.Label(info_frame,
                                     text=f"Prozentuale Veränderung: {daily_percent:.2f}%",
                                     font=("Helvetica", 14),
                                     foreground="white")
            lbl_daily_pct.grid(row=1, column=0, pady=(5, 5), sticky="ew")

            lbl_total = tb.Label(info_frame,
                                 text=f"Gesamtwert: {current_total:.2f} USD",
                                 font=("Helvetica", 16, "bold"),
                                 foreground="white")
            lbl_total.grid(row=2, column=0, pady=(5, 5), sticky="ew")

            lbl_overall = tb.Label(info_frame,
                                   text=f"Gesamtrendite (1 Monat): {overall_return:.2f}%",
                                   font=("Helvetica", 14),
                                   foreground="white")
            lbl_overall.grid(row=3, column=0, pady=(5, 5), sticky="ew")

            lbl_top = tb.Label(info_frame,
                               text=f"Top Performer: {top_ticker} ({top_pct:.2f}%)",
                               font=("Helvetica", 14),
                               foreground="white")
            lbl_top.grid(row=4, column=0, pady=(5, 5), sticky="ew")

            lbl_flop = tb.Label(info_frame,
                                text=f"Flop Performer: {flop_ticker} ({flop_pct:.2f}%)",
                                font=("Helvetica", 14),
                                foreground="white")
            lbl_flop.grid(row=5, column=0, pady=(5, 10), sticky="ew")

            # --- Untere Zeile (über beide Spalten): Liniendiagramm ---
            line_frame = tb.Frame(self.grid_container)
            line_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
            line_frame.columnconfigure(0, weight=1)
            line_frame.rowconfigure(0, weight=1)

            if total_values.empty:
                raise ValueError("Keine gültigen Daten für das Liniendiagramm verfügbar.")

            fig_line = Figure(facecolor=bg_color)
            ax_line = fig_line.add_subplot(111)
            ax_line.plot(total_values.index, total_values.values, label="Portfolio", color="#4a90e2")
            ax_line.set_title("Portfolio-Veränderungen", color="white")
            ax_line.set_xlabel("Datum", color="white")
            ax_line.set_ylabel("Wert in USD", color="white")
            ax_line.tick_params(colors="white")
            ax_line.legend(facecolor=bg_color, labelcolor="white")
            fig_line.tight_layout()

            canvas_line = FigureCanvasTkAgg(fig_line, master=line_frame)
            canvas_line.draw()
            canvas_line.get_tk_widget().pack(fill="both", expand=True)
        except Exception as e:
            self.show_error(e)

    def show_error(self, error: Exception):
        """
        Zeigt eine Fehlermeldung im Dashboard an.
        """
        error_label = tb.Label(self.grid_container,
                               text=f"Fehler beim Laden der Daten: {error}",
                               font=("Helvetica", 14),
                               foreground="red")
        error_label.grid(row=0, column=0, columnspan=2, pady=20, sticky="nsew")

    def get_portfolio_data(self) -> pd.DataFrame:
        """
        Ruft die Daten für alle im Portfolio vorhandenen Ticker ab.
        """
        data_frames = []
        for item in self.app.portfolio_data:
            ticker = item["ticker"]
            quantity = item["quantity"]
            data = fetch_stock_history(ticker, quantity, period="1mo")
            data_frames.append(data)
        return pd.concat(data_frames, ignore_index=True)

    def stop_threads(self):
        """
        Beendet laufende Tasks des ThreadPoolExecutors.
        """
        if self.future and not self.future.done():
            self.future.cancel()
        self.executor.shutdown(wait=False)


class MarketPage(tb.Frame):
    """
    Seite zum Abrufen und Anzeigen von Marktdaten für ein gegebenes Ticker-Symbol
    und einen Zeitraum.
    """

    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.future = None

        title = tb.Label(self, text="Aktueller Markt", font=("Helvetica", 24, "bold"))
        title.pack(pady=20)

        # Container zum Zentrieren der Eingaben
        input_container = tb.Frame(self)
        input_container.pack(pady=10, anchor="center")

        ticker_frame = tb.Frame(input_container)
        ticker_frame.pack(pady=5, anchor="center")
        ticker_label = tb.Label(ticker_frame, text="Ticker-Symbol:")
        ticker_label.pack(side="left", padx=5)
        self.ticker_entry = tb.Entry(ticker_frame, width=15)
        self.ticker_entry.pack(side="left", padx=5)
        self.ticker_entry.insert(0, "AAPL")

        period_frame = tb.Frame(input_container)
        period_frame.pack(pady=5, anchor="center")
        period_label = tb.Label(period_frame, text="Zeitraum:")
        period_label.pack(side="left", padx=5)
        self.period_var = tb.StringVar()
        self.period_combo = tb.Combobox(
            period_frame,
            textvariable=self.period_var,
            width=12,
            values=["1d", "5d", "1mo", "3mo", "6mo", "1y", "5y", "max"],
        )
        self.period_combo.set("1mo")
        self.period_combo.pack(side="left", padx=5)

        btn_fetch = tb.Button(input_container, text="Daten abrufen", command=self.fetch_data, bootstyle="primary")
        btn_fetch.pack(pady=10, anchor="center")

        self.price_label = tb.Label(self, text="")
        self.price_label.pack(pady=5, anchor="center")

        self.chart_frame = tb.Frame(self)
        self.chart_frame.pack(fill="both", expand=True, pady=10)

    def fetch_data(self):
        """
        Startet den asynchronen Abruf der Marktdaten.
        """
        ticker_symbol = self.ticker_entry.get().strip().upper()
        period = self.period_var.get()

        if not ticker_symbol:
            return

        self.future = self.executor.submit(self.fetch_market_data, ticker_symbol, period)

    def fetch_market_data(self, ticker_symbol: str, period: str):
        """
        Holt die Marktdaten mit yfinance und aktualisiert die UI.
        """
        try:
            stock = yf.Ticker(ticker_symbol)
            data = stock.history(period=period)
            if data.empty:
                return

            current_price = data["Close"].iloc[-1]
            self.after(0, lambda: self.price_label.config(
                text=f"Aktueller Kurs von {ticker_symbol}: {current_price:.2f} USD"))
            self.after(0, lambda: self.plot_chart(data, ticker_symbol, period))
        except Exception as e:
            logging.exception("Fehler beim Abrufen von Marktdaten:")

    def plot_chart(self, data: pd.DataFrame, ticker_symbol: str, period: str):
        """
        Zeichnet das Liniendiagramm für die Schlusskurse.
        """
        for widget in self.chart_frame.winfo_children():
            widget.destroy()

        fig = Figure()
        ax = fig.add_subplot(111)
        ax.plot(data.index, data["Close"], label="Schlusskurs", color="#4a90e2")
        ax.set_title(f"{ticker_symbol} – Schlusskursverlauf ({period})", color="white")
        ax.set_xlabel("Datum", color="white")
        ax.set_ylabel("Preis (USD)", color="white")
        ax.tick_params(colors="white")
        ax.legend(facecolor=self.app.cget("background"), labelcolor="white")
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def stop_threads(self):
        """
        Beendet laufende Tasks des ThreadPoolExecutors.
        """
        if self.future and not self.future.done():
            self.future.cancel()
        self.executor.shutdown(wait=False)


class PortfolioPage(tb.Frame):
    """
    Seite zum Hinzufügen und Anzeigen von Portfolio-Einträgen.
    """

    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app

        title = tb.Label(self, text="Ihr Portfolio", font=("Helvetica", 24, "bold"))
        title.pack(pady=20)

        # Container zum Zentrieren der Eingaben
        input_container = tb.Frame(self)
        input_container.pack(pady=10, anchor="center")

        form_frame = tb.Frame(input_container)
        form_frame.grid(row=0, column=0, pady=5)
        label_ticker = tb.Label(form_frame, text="Ticker:")
        label_ticker.grid(row=0, column=0, padx=5)
        self.ticker_entry = tb.Entry(form_frame, width=10)
        self.ticker_entry.grid(row=0, column=1, padx=5)

        label_quantity = tb.Label(form_frame, text="Anzahl:")
        label_quantity.grid(row=0, column=2, padx=5)
        self.quantity_entry = tb.Entry(form_frame, width=5)
        self.quantity_entry.grid(row=0, column=3, padx=5)

        btn_add = tb.Button(input_container, text="Hinzufügen", command=self.add_ticker, bootstyle="primary")
        btn_add.grid(row=1, column=0, pady=5)

        # Verwende ein eigenes Frame für die Anzeige der Einträge mit Grid
        self.portfolio_frame = tb.Frame(self)
        self.portfolio_frame.pack(pady=10, fill="both", expand=True)

        self.update_portfolio()

    def add_ticker(self):
        """
        Fügt einen neuen Ticker mit der angegebenen Anzahl dem Portfolio hinzu.
        Es werden keine Popup-Nachrichten oder Sounds abgespielt.
        """
        new_ticker = self.ticker_entry.get().strip().upper()
        quantity = self.quantity_entry.get().strip()

        if new_ticker and quantity.isdigit():
            quantity = int(quantity)
            if not any(item["ticker"] == new_ticker for item in self.app.portfolio_data):
                self.app.portfolio_data.append({"ticker": new_ticker, "quantity": quantity})
            self.update_portfolio()
            self.app.frames["DashboardPage"].update_dashboard()

        self.ticker_entry.delete(0, "end")
        self.quantity_entry.delete(0, "end")

    def update_portfolio(self):
        """
        Aktualisiert die visuelle Portfolio-Liste.
        """
        # Entferne alle alten Widgets
        for widget in self.portfolio_frame.winfo_children():
            widget.destroy()

        if not self.app.portfolio_data:
            lbl = tb.Label(self.portfolio_frame, text="Ihr Portfolio ist leer.", anchor="center")
            lbl.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        else:
            for idx, item in enumerate(self.app.portfolio_data):
                ticker_card = tb.Frame(self.portfolio_frame, bootstyle="info", padding=10)
                ticker_card.grid(row=idx, column=0, padx=10, pady=5, sticky="ew")
                ticker_card.columnconfigure(0, weight=1)
                lbl = tb.Label(ticker_card,
                               text=f"{item['ticker']} – {item['quantity']} Stück",
                               font=("Helvetica", 14, "bold"),
                               anchor="w")
                lbl.grid(row=0, column=0, sticky="w")

        # Stelle sicher, dass sich das Portfolio-Frame über die volle Breite erstreckt
        self.portfolio_frame.update_idletasks()
        self.portfolio_frame.configure(width=self.winfo_width())


if __name__ == "__main__":
    app = App()
    app.mainloop()
