import ttkbootstrap as tb
from ttkbootstrap.constants import *
import yfinance as yf
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from tkinter import PhotoImage, messagebox
import pandas as pd
import threading
import random

class App(tb.Window):
    def __init__(self):
        super().__init__(themename="darkly")
        self.title("Aktien & ETF Portfolio")
        self.geometry("1200x800")

        # Vollbild im Fenster-Modus erzwingen
        self.state('zoomed')

        # Flags für Threads
        self.running = True

        # Portfolio-Daten initialisieren
        self.portfolio_data = []

        # Sidebar erstellen
        self.sidebar = tb.Frame(self, bootstyle="secondary", width=250)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Hauptbereich erstellen
        self.container = tb.Frame(self, padding=15)
        self.container.pack(side="right", fill="both", expand=True)

        # Menü-Elemente erstellen
        self.create_sidebar()

        # Seiten-Frames verwalten
        self.frames = {}
        for F in (DashboardPage, MarketPage, PortfolioPage):
            page_name = F.__name__
            frame = F(parent=self.container, app=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        # Starte mit der Dashboard-Seite
        self.show_frame("DashboardPage")


    def create_sidebar(self):
        # Dashboard-Button
        btn_dashboard = tb.Button(
            self.sidebar,
            text=" Dashboard",
            compound="left",
            command=lambda: self.show_frame("DashboardPage"),
            bootstyle="outline-primary",
            width=220,
        )
        btn_dashboard.pack(pady=(20, 10), padx=10)

        # Markt-Button
        btn_market = tb.Button(
            self.sidebar,
            text=" Markt",
            compound="left",
            command=lambda: self.show_frame("MarketPage"),
            bootstyle="outline-primary",
            width=220,
        )
        btn_market.pack(pady=10, padx=10)

        # Portfolio-Button
        btn_portfolio = tb.Button(
            self.sidebar,
            text=" Portfolio",
            compound="left",
            command=lambda: self.show_frame("PortfolioPage"),
            bootstyle="outline-primary",
            width=220,
        )
        btn_portfolio.pack(pady=10, padx=10)

    def show_frame(self, page_name):
        frame = self.frames[page_name]
        frame.tkraise()

    def on_close(self):
        """Beendet die Anwendung und alle laufenden Threads sicher."""
        self.running = False
        for frame in self.frames.values():
            if hasattr(frame, "stop_threads"):
                frame.stop_threads()
        self.destroy()


class DashboardPage(tb.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.thread = None

        # Überschrift
        title = tb.Label(self, text="Dashboard", font=("Helvetica", 24, "bold"))
        title.pack(pady=10)

        # Layout: Hauptcontainer
        self.grid_container = tb.Frame(self)
        self.grid_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Spalten- und Zeilenkonfiguration
        self.grid_container.columnconfigure(0, weight=1)
        self.grid_container.columnconfigure(1, weight=1)
        self.grid_container.rowconfigure(0, weight=1)
        self.grid_container.rowconfigure(1, weight=1)

        # Datenaktualisierung prüfen
        self.update_dashboard()

    def update_dashboard(self):
        for widget in self.grid_container.winfo_children():
            widget.destroy()

        portfolio_data = self.app.portfolio_data

        if not portfolio_data:
            empty_label = tb.Label(self.grid_container, text="Ihr Portfolio ist leer. Fügen Sie Aktien oder ETFs hinzu.", font=("Helvetica", 14))
            empty_label.grid(row=0, column=0, columnspan=2, pady=20)
            return

        self.thread = threading.Thread(target=self.load_and_display_data, daemon=True)
        self.thread.start()

    def load_and_display_data(self):
        try:
            data = self.get_portfolio_data()
            self.after(0, lambda: self.display_charts(data))
        except Exception as e:
            self.after(0, lambda: self.show_error(e))

    def display_charts(self, data):
        try:
            # Position 1: Kreisdiagramm (oben links)
            pie_frame = tb.Frame(self.grid_container)
            pie_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
            composition = data.groupby('Ticker')['TotalValue'].sum()

            if composition.empty:
                raise ValueError("Keine gültigen Daten für das Kreisdiagramm verfügbar.")

            fig_pie = Figure(figsize=(5, 5))
            ax_pie = fig_pie.add_subplot(111)
            ax_pie.pie(composition, labels=composition.index, autopct='%1.1f%%')
            ax_pie.set_title("Portfolio-Zusammensetzung")

            canvas_pie = FigureCanvasTkAgg(fig_pie, master=pie_frame)
            canvas_pie.draw()
            canvas_pie.get_tk_widget().pack(fill="both", expand=True)

            # Position 2: Tagesveränderung (oben rechts)
            change_frame = tb.Frame(self.grid_container)
            change_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
            total_change = data.groupby('Date')['TotalValue'].sum().diff().iloc[-1]
            change_label = tb.Label(
                change_frame,
                text=f"Tagesveränderung: {total_change:.2f} USD",
                font=("Helvetica", 16, "bold"),
                foreground="green" if total_change > 0 else "red",
            )
            change_label.pack(expand=True)

            # Position 3: Liniendiagramm (unten über die gesamte Breite)
            line_frame = tb.Frame(self.grid_container)
            line_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
            total_values = data.groupby('Date')['TotalValue'].sum()

            if total_values.empty:
                raise ValueError("Keine gültigen Daten für das Liniendiagramm verfügbar.")

            fig_line = Figure(figsize=(10, 5))
            ax_line = fig_line.add_subplot(111)
            ax_line.plot(total_values.index, total_values.values, label="Portfolio", color="#4a90e2")
            ax_line.set_title("Portfolio-Veränderungen")
            ax_line.set_xlabel("Datum")
            ax_line.set_ylabel("Wert in USD")
            ax_line.legend()

            canvas_line = FigureCanvasTkAgg(fig_line, master=line_frame)
            canvas_line.draw()
            canvas_line.get_tk_widget().pack(fill="both", expand=True)
        except Exception as e:
            self.show_error(e)

    def show_error(self, error):
        error_label = tb.Label(self.grid_container, text=f"Fehler beim Laden der Daten: {error}", font=("Helvetica", 14), foreground="red")
        error_label.grid(row=0, column=0, columnspan=2, pady=20)

    def get_portfolio_data(self):
        data_frames = []
        for item in self.app.portfolio_data:
            ticker = item['ticker']
            quantity = item['quantity']
            try:
                stock = yf.Ticker(ticker)
                history = stock.history(period="1mo").reset_index()
                if history.empty:
                    raise ValueError(f"Keine Daten für {ticker} verfügbar.")
                history['Ticker'] = ticker
                history['TotalValue'] = history['Close'] * quantity
                data_frames.append(history)
            except Exception as e:
                print(f"Fehler beim Abrufen von Daten für {ticker}: {e}")
                dates = pd.date_range(start="2023-01-01", periods=30)
                values = [random.uniform(100, 200) for _ in range(30)]
                test_data = pd.DataFrame({"Date": dates, "Close": values, "Ticker": ticker, "TotalValue": [v * quantity for v in values]})
                data_frames.append(test_data)
        return pd.concat(data_frames, ignore_index=True)

    def stop_threads(self):
        if self.thread and self.thread.is_alive():
            self.thread.join()


class MarketPage(tb.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        title = tb.Label(self, text="Aktueller Markt", font=("Helvetica", 24, "bold"))
        title.pack(pady=20)

        ticker_frame = tb.Frame(self)
        ticker_frame.pack(pady=10)
        ticker_label = tb.Label(ticker_frame, text="Ticker-Symbol:")
        ticker_label.pack(side="left", padx=5)
        self.ticker_entry = tb.Entry(ticker_frame, width=15)
        self.ticker_entry.pack(side="left", padx=5)
        self.ticker_entry.insert(0, "AAPL")

        period_frame = tb.Frame(self)
        period_frame.pack(pady=10)
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

        btn_fetch = tb.Button(self, text="Daten abrufen", command=self.fetch_data, bootstyle="primary")
        btn_fetch.pack(pady=10)

        self.price_label = tb.Label(self, text="")
        self.price_label.pack(pady=5)

        self.chart_frame = tb.Frame(self)
        self.chart_frame.pack(fill="both", expand=True, pady=10)

    def fetch_data(self):
        ticker_symbol = self.ticker_entry.get().strip().upper()
        period = self.period_var.get()

        if not ticker_symbol:
            messagebox.showerror("Fehler", "Bitte geben Sie ein Ticker-Symbol ein!")
            return

        try:
            stock = yf.Ticker(ticker_symbol)
            data = stock.history(period=period)
            if data.empty:
                messagebox.showinfo("Info", "Keine Daten gefunden. Bitte überprüfen Sie das Ticker-Symbol oder den Zeitraum.")
                return

            current_price = data['Close'].iloc[-1]
            self.price_label.config(text=f"Aktueller Kurs von {ticker_symbol}: {current_price:.2f} USD")
            self.plot_chart(data, ticker_symbol, period)
        except Exception as e:
            messagebox.showerror("Fehler", f"Es trat ein Fehler auf: {e}")

    def plot_chart(self, data, ticker_symbol, period):
        for widget in self.chart_frame.winfo_children():
            widget.destroy()

        fig = Figure(figsize=(10, 5))
        ax = fig.add_subplot(111)
        ax.plot(data.index, data['Close'], label="Schlusskurs", color="#4a90e2")
        ax.set_title(f"{ticker_symbol} – Schlusskursverlauf ({period})")
        ax.set_xlabel("Datum")
        ax.set_ylabel("Preis (USD)")
        ax.legend()

        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)


class PortfolioPage(tb.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        title = tb.Label(self, text="Ihr Portfolio", font=("Helvetica", 24, "bold"))
        title.pack(pady=20)

        form_frame = tb.Frame(self)
        form_frame.pack(pady=10)
        label_ticker = tb.Label(form_frame, text="Ticker:")
        label_ticker.pack(side="left", padx=5)
        self.ticker_entry = tb.Entry(form_frame, width=10)
        self.ticker_entry.pack(side="left", padx=5)

        label_quantity = tb.Label(form_frame, text="Anzahl:")
        label_quantity.pack(side="left", padx=5)
        self.quantity_entry = tb.Entry(form_frame, width=5)
        self.quantity_entry.pack(side="left", padx=5)

        btn_add = tb.Button(form_frame, text="Hinzufügen", command=self.add_ticker, bootstyle="primary")
        btn_add.pack(side="left", padx=5)

        self.portfolio_frame = tb.Frame(self)
        self.portfolio_frame.pack(pady=10, fill="both", expand=True)

        self.portfolio = []
        self.update_portfolio()

    def add_ticker(self):
        new_ticker = self.ticker_entry.get().strip().upper()
        quantity = self.quantity_entry.get().strip()

        if not new_ticker or not quantity.isdigit():
            messagebox.showerror("Fehler", "Bitte geben Sie einen gültigen Ticker und eine Anzahl ein!")
            return

        quantity = int(quantity)
        if new_ticker in [item['ticker'] for item in self.app.portfolio_data]:
            messagebox.showinfo("Info", f"{new_ticker} ist bereits im Portfolio!")
        else:
            self.portfolio.append(new_ticker)
            self.app.portfolio_data.append({"ticker": new_ticker, "quantity": quantity})
            messagebox.showinfo("Erfolg", f"{new_ticker} wurde hinzugefügt!")
            self.ticker_entry.delete(0, "end")
            self.quantity_entry.delete(0, "end")
            self.update_portfolio()
            self.app.frames["DashboardPage"].update_dashboard()

    def update_portfolio(self):
        for widget in self.portfolio_frame.winfo_children():
            widget.destroy()

        if not self.portfolio:
            lbl = tb.Label(self.portfolio_frame, text="Ihr Portfolio ist leer.")
            lbl.pack()
        else:
            for item in self.app.portfolio_data:
                ticker_card = tb.Frame(self.portfolio_frame, bootstyle="info", padding=10)
                ticker_card.pack(fill="x", pady=5, padx=10)

                lbl = tb.Label(ticker_card, text=f"{item['ticker']} – {item['quantity']} Stück", font=("Helvetica", 14, "bold"))
                lbl.pack(anchor="w")


if __name__ == "__main__":
    app = App()
    app.mainloop()
