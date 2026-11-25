import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle
plt.rcParams["font.family"] = "Liberation Sans"
fig, ax = plt.subplots(figsize=(16, 10.2), dpi=200)
ax.set_xlim(0, 162); ax.set_ylim(4, 100); ax.axis("off"); ax.set_aspect("equal")

# Protoboard
ax.add_patch(FancyBboxPatch((4, 38), 144, 58, boxstyle="round,pad=0.5", fc="#f1efe9", ec="#b9b5aa", lw=1.2))
for row in (41, 92.5):
    ax.plot([7, 145], [row, row], color="#c0392b" if row > 20 else "#2c6fbb", lw=1)
for y in [43 + 2.6 * i for i in range(19)]:
    for x in range(8, 145, 2):
        ax.add_patch(Rectangle((x, y), 0.7, 0.7, fc="#cfcac0", ec="none"))
ax.text(76, 34.5, "Protoboard", ha="center", fontsize=10, color="#555")

# Módulo LCD
ax.add_patch(FancyBboxPatch((10, 52), 48, 40, boxstyle="round,pad=0.4", fc="#d63a3a", ec="#8e1f1f", lw=1.5))
ax.add_patch(Rectangle((15, 60), 38, 29, fc="#1f2a44", ec="#111", lw=1.2))
ax.text(34, 76, "LCD 240 × 320\nILI9341 + toque XPT2046", ha="center", va="center", color="white", fontsize=10.5)
lcd_pins = ["VCC", "GND", "CS", "RESET", "DC", "SDI", "SCK", "LED", "SDO", "T_CLK", "T_CS", "T_DIN", "T_DO", "T_IRQ"]
lcd_x = {p: 13.5 + i * 3.2 for i, p in enumerate(lcd_pins)}
for p, x in lcd_x.items():
    ax.add_patch(Rectangle((x - 0.8, 53), 1.6, 1.6, fc="#e5c26b", ec="#7a5b12", lw=0.8))
    ax.text(x, 56.2, p, rotation=90, ha="center", va="bottom", fontsize=7.2, color="white")
ax.text(34, 93.4, "Módulo display SPI (J2, 14 pinos)", ha="center", fontsize=10, bbox=dict(fc="white", ec="none", pad=1))

# Placa ESP32-S3
ax.add_patch(FancyBboxPatch((84, 54), 60, 26, boxstyle="round,pad=0.4", fc="#4b2a6b", ec="#2a173d", lw=1.5))
ax.add_patch(Rectangle((88, 60), 22, 16, fc="#c9ccd1", ec="#7d8187", lw=1))
ax.text(99, 68, "ESP32-S3\nWROOM-1", ha="center", va="center", fontsize=9.5)
ax.add_patch(Circle((120, 70), 1.2, fc="#e74c3c", ec="none"))
ax.text(126, 70, "LED de energia", va="center", fontsize=8, color="white")
esp_pins = ["3V3", "3V3", "RST", "4", "5", "6", "7", "15", "16", "17", "18", "8", "3", "46", "9", "10", "11", "12", "13", "14", "5V", "GND"]
esp_x = {}
for i, p in enumerate(esp_pins):
    x = 86.5 + i * 2.65
    esp_x.setdefault(p, x)
    ax.add_patch(Rectangle((x - 0.7, 55), 1.4, 1.4, fc="#e5c26b", ec="#7a5b12", lw=0.8))
    ax.text(x, 57.5, p, rotation=90, ha="center", va="bottom", fontsize=7, color="white")
ax.text(114, 82.5, "Placa ESP32-S3 (fileira de pinos 3V3 até GND)", ha="center", fontsize=10, bbox=dict(fc="white", ec="none", pad=1))
# USB-C e cabo
ax.add_patch(Rectangle((143, 62), 4, 6, fc="#9aa0a6", ec="#555"))
ax.plot([147, 154, 154], [65, 65, 84], color="#7fd6c2", lw=5, solid_capstyle="round")
ax.add_patch(FancyBboxPatch((146, 84), 15, 8, boxstyle="round,pad=0.3", fc="#eef2f7", ec="#555"))
ax.text(153.5, 88, "Computador\n(USB)", ha="center", va="center", fontsize=9)
ax.text(155.5, 72, "cabo USB-C\nenergia\ne dados", fontsize=8, va="center")

# Ligações: pino do LCD -> pino da ESP32-S3
links = [("VCC", "3V3", "#d62728"), ("LED", "3V3", "#ff7f0e"), ("GND", "GND", "#111111"),
         ("CS", "10", "#1f77b4"), ("DC", "9", "#17becf"), ("RESET", "8", "#9467bd"),
         ("SDI", "11", "#2ca02c"), ("SCK", "12", "#bcbd22"), ("SDO", "13", "#8c564b"),
         ("T_CLK", "12", "#bcbd22"), ("T_DIN", "11", "#2ca02c"), ("T_DO", "13", "#8c564b"),
         ("T_CS", "7", "#e377c2"), ("T_IRQ", "6", "#7f7f7f")]
for k, (lp, ep, c) in enumerate(links):
    y = 50.5 - k * 0.42 - (0 if k < 3 else 0.3)
    x1, x2 = lcd_x[lp], esp_x[ep] + ((k % 3) - 1) * 0.35
    ax.plot([x1, x1, x2, x2], [53, y, y, 55], color=c, lw=1.6, solid_joinstyle="round")
# Legenda
leg = [("VCC e LED", "3V3", "#d62728"), ("GND", "GND", "#111111"), ("CS", "GPIO10", "#1f77b4"),
       ("DC", "GPIO9", "#17becf"), ("RESET", "GPIO8", "#9467bd"), ("SDI e T_DIN (MOSI)", "GPIO11", "#2ca02c"),
       ("SCK e T_CLK", "GPIO12", "#bcbd22"), ("SDO e T_DO (MISO)", "GPIO13", "#8c564b"),
       ("T_CS", "GPIO7", "#e377c2"), ("T_IRQ", "GPIO6", "#7f7f7f")]
ax.text(10, 29, "Ligações com fios jumper (pino do display  →  pino da ESP32-S3)", fontsize=10.5, weight="bold")
for i, (a, b, c) in enumerate(leg):
    col, row = divmod(i, 5)
    x0, y = 10 + col * 70, 24.5 - row * 4
    ax.plot([x0, x0 + 5], [y, y], color=c, lw=3.5)
    ax.text(x0 + 6.5, y, f"{a}  →  {b}", va="center", fontsize=9.5)
fig.savefig("ligacoes.png", bbox_inches="tight", facecolor="white")
