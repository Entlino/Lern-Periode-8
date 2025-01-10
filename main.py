import tkinter as tk
from tkinter import ttk
import yfinance as yf


class FinanceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Finanzdaten App")
        self.root.geometry("600x450")  # Fenstergröße
        self.root.configure(bg="#212121")  # Dunkler Hintergrund für modernes Design
        self.root.resizable(False, False)  # Verhindert das Vergrößern des Fensters

        # Titel
        self.title_label = tk.Label(root, text="Aktienkursanzeige", font=("Segoe UI", 20, "bold"), bg="#212121",
                                    fg="#ffffff")
        self.title_label.pack(pady=20)

        # Eingabe für den Firmennamen oder Tickersymbol
        self.symbol_label = tk.Label(root, text="Gib einen Firmennamen ein:", font=("Segoe UI", 12), bg="#212121",
                                     fg="#ffffff")
        self.symbol_label.pack(pady=5)

        self.symbol_entry = tk.Entry(root, width=30, font=("Segoe UI", 14), borderwidth=2, relief="solid", fg="#ffffff",
                                     bg="#333333")
        self.symbol_entry.pack(pady=10)

        # Button zum Abrufen der Daten
        self.fetch_button = ttk.Button(root, text="Daten abrufen", command=self.fetch_data, style="TButton")
        self.fetch_button.pack(pady=20)

        # Label für das Ergebnis
        self.result_label = tk.Label(root, text="Hier wird der Kurs angezeigt...", font=("Segoe UI", 14), bg="#212121",
                                     fg="#ffffff")
        self.result_label.pack(pady=20)

        # Automatische Aktualisierung: Checkbox
        self.auto_update = tk.BooleanVar()
        self.auto_update_check = ttk.Checkbutton(
            root, text="Automatisch alle 10 Sekunden aktualisieren", variable=self.auto_update,
            command=self.toggle_auto_update, style="TCheckbutton"
        )
        self.auto_update_check.pack(pady=10)

        # Timer für automatische Updates
        self.update_interval = 10000  # 10 Sekunden in Millisekunden
        self.auto_update_job = None

        # Style für Button und andere Widgets
        self.style = ttk.Style()
        self.style.configure("TButton", padding=8, relief="flat", background="#4CAF50", foreground="white",
                             font=("Segoe UI", 14, "bold"))
        self.style.map("TButton", background=[('active', '#45a049')])

        self.style.configure("TCheckbutton", font=("Segoe UI", 12), foreground="white", background="#212121", padding=5)

        # Liste von Firmen und ihren Tickersymbolen laden
        self.company_tickers = self.load_company_tickers()

        # Binde die Enter-Taste an die `fetch_data`-Methode
        self.symbol_entry.bind("<Return>", self.on_enter)

    def load_company_tickers(self):
        """
        Lädt eine Liste von Firmen und ihren Tickersymbolen.
        Hier ein einfaches Beispiel mit ein paar Unternehmen.
        """
        return {"apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL", "tesla": "TSLA"}  # Beispielhafte Daten

    def fetch_data(self):
        """
        Holt den aktuellen Kurs des eingegebenen Tickersymbols und zeigt ihn in der GUI an.
        """
        company_name = self.symbol_entry.get().strip().lower()  # Eingabe vom Benutzer, in Kleinbuchstaben umgewandelt
        if not company_name:
            self.result_label.config(text="Bitte gib einen Firmennamen oder Tickersymbol ein.")
            return

        # Suche nach dem Ticker, wenn der Benutzer den Firmennamen eingegeben hat
        if company_name in self.company_tickers:
            symbol = self.company_tickers[company_name]
        else:
            symbol = company_name

        try:
            # Abrufen der Daten
            stock = yf.Ticker(symbol)
            hist_data = stock.history(period="1d")

            if hist_data.empty:
                self.result_label.config(text=f"Keine Daten für {symbol.upper()} gefunden.")
                return

            price = hist_data['Close'].iloc[-1]
            self.result_label.config(text=f"Aktueller Kurs von {symbol.upper()}: {price:.2f} USD")
        except Exception as e:
            self.result_label.config(text="Fehler beim Abrufen der Daten.")
            print(f"Error: {e}")

    def on_enter(self, event=None):
        """
        Wird aufgerufen, wenn die Enter-Taste gedrückt wird.
        """
        self.fetch_data()

    def toggle_auto_update(self):
        """
        Aktiviert oder deaktiviert die automatische Aktualisierung.
        """
        if self.auto_update.get():
            self.start_auto_update()
        else:
            self.stop_auto_update()

    def start_auto_update(self):
        """
        Startet den Timer für die automatische Aktualisierung.
        """
        self.fetch_data()  # Abrufen der Daten
        self.auto_update_job = self.root.after(self.update_interval, self.start_auto_update)

    def stop_auto_update(self):
        """
        Stoppt den Timer für die automatische Aktualisierung.
        """
        if self.auto_update_job:
            self.root.after_cancel(self.auto_update_job)
            self.auto_update_job = None


# Hauptprogramm
if __name__ == "__main__":
    root = tk.Tk()
    app = FinanceApp(root)
    root.mainloop()