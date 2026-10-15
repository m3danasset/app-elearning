"""Ikon Blender untuk sidebar (gambar disematkan di sini, jadi ikut terbawa update.bat).

Ukuran mengikuti foto profil murid: 56 px (sidebar terbuka) dan 44 px (sidebar dilipat).
Pengecilan memakai alpha ter-premultiply + LANCZOS, jadi tepinya halus (tidak pecah-pecah)
dan tidak ada garis putih di pinggir gambar.
"""

import base64
import io

from elearning import config as C

SIZE_EXPANDED = 56   # sama dengan Avatar di header sidebar terbuka
SIZE_COLLAPSED = 44  # sama dengan Avatar di sidebar dilipat

_DATA = (
    "iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAYAAABw4pVUAAAACXBIWXMAAAsTAAALEwEAmpwYAAAfBklEQVR4nO1deZhVxZX/nbr3"
    "vn3pvZvuBhoQkN0WRDSiIa6YSNxANJmYMZPFSZyYbXRGM2YSo5kkahJ18kWTiQm4Ro3GHTXiAiIBZIdma+iG3te3v3fvrTN/1HtN"
    "Q+ju97obab/w+773Nd3UrVv3/qpOVZ3zO/WImXESIwfiRDfgJI7ESUJGGE4SMsJwkpARhpOEjDCcJGSE4SQhIwwnCRlhOEnICMNJ"
    "QkYYThIywnCSkBGGk4SMMOgAIJt2Depi8gQh6zbB3r0KonAsZPNucLQDlFcOUVABjncDpAFWCpyMAHQk/xzrgjbxE9AmfgIc68rx"
    "5gRoBuTOlZDNezyyaffnYMbPYDM5lpzeelE8fi2c3mWieGyckzFwPARyeMDJqPoZaQcVjQXsFGDbANtgZhAE2IqDAqWqjDcPHO0C"
    "aYb6PVgK7mwAlU0EpASsJKAZh3+aCUDoQDIKGW6FKJkACAGAoE0+F7AtgOUxH0mMrVaEnDgwIDT1oVwGKwO6A+QtgF236cv2hy/8"
    "mKVdDGZA0wDLhL1n9ZfIV/gD/fTLvyEqZzzLZgL4GIQaTrDJIiAVP/xvyvYjQIFSWO/94Rrr3UceYpbF5AmCPEGQ0wfy5oMCZYCZ"
    "GGW+/+gz1rpnf0KefMATAKR9Qp94IJzQEUJOL7h1H2TtesBwAKmEeuEDweGBbNwZNP/668fg9II8QWU+jgADrgDISsKuWXkLJ8PT"
    "9akX3ECBkhak4iN2tJxYk6U7wakY7D2rQMFRgO4AktEBLyNvPmT9lmkcDwvyFR6DjDRYApoDlFcOWb/502Zb3VZ97pLLRXHVao51"
    "j0hSTqzJYgkYLoAlONwCYglROBaUNwrkyevzA8MNMerU3eQOAvHuAeYfBphB/mKwmSi23l++yt72xq3kKwS5fH1OsCcKJ3hSh+ql"
    "hgswk5Ate0FCh6iYBvIEwckYYCUAHG3GGFQwr1XvPPgv5ss/+y3pLsDh7v/lMoPcAcCMw9r6+t0i3DbTmLf0S+QviXNXI4CRMVpG"
    "xj6EGXB4AM2AvWc1rLVPQu5eBZhxkMuvlo12CrBNQJqAbYHDLdCmX/g7fe6SmzgRAhLhgVdq6RFJwRLI+k3Xpt54YBs3755N+eVq"
    "qToCTNjIIARQL0voIE8+YKVg7Xkf1obnYO/9AJAS5CsCDKfqyESAbYNjXRATP/GAcfY/LYCmRzjSlsV9GACpfUZ387jUyofW2bXr"
    "/oV8RWqU9TUffUQYOYT0gAHDqYhJxWGniZF7PwBsC+QrVJM/AFgmONIBKqpaqZ+5dJooGLOWw609L73/28h0XS5Yax5/2Frz+EPk"
    "9IICxSd0aTwCCclAzS3kKwCSUVi734P94V9g71sL2KZ6cQ6X2mGHWkAuX50+/4tnahPmPcHhNmXisjBh5PSC3EHY+9Z+2XrvkVWy"
    "69AplFeuRuEJMGEjmJA0OENMITgZhb3rPVgbnofcuRIwE2qi1p3gSAdAAvqcK6/Vp11wCxIRNa+ILOYVoamlcdOus62VD2+RDTuu"
    "EYHSNOEfrQkb+YRkkCHGXwik4rA2vgx706tAqEmNBodbTfbxCMTk+T/VqhddBaHFOdSWnVuGJchfAhbCZa15/AlzzeP3kMMD8vaz"
    "zzkO+PgQkkGvEYNUDLK1FtxRD452AIluwEqA4yGIsknP6ud8sVrkV+zjaHuWdUvlevEEYW959dvW+4+uQDxUSoHiw/c+zvj4EdIb"
    "ugMw3GoExEOQjTWQzbuBaAe4qwGi9JQa/fwbp1B+5Wvc1aQm62yWxsIA5VVANu26MPXqvdu5bf85PZ6E42zCPt6EZJB2xUPogJkA"
    "dzWCox2QBzaAQ80p47TPXKLP/uzPYcaVa2ZAfxkDYGXCktECc/Wj71qbXrqdXH6QO3hcSRnenbrQlTnxBJVJIUq/pKSaXPvrnSTU"
    "HAAgvdno4x4ESFZ2XVrHeLnp35nB8RC47QDIWwAxYd73yHAts2re/ROs1CRoWTw6S+WqMROwN7/yIw41n6XPvuJq8hbEB7x2kBg6"
    "ISxVbMJfDLTuA8Kt8+1Y9zjuPOjgVJzTL5pgJajfvQEJQNpgM9H/qCViMBPMBKme2l+dBDYTgkMtkA3bbcqvOEB55eu5ff+kfkk/"
    "1vPll0M27rzUfP3+nfqshUu0ymkfyFDrsM8rQyREOe2IBKxNL/7A3rvmGiSjp7KZhM3y8IjIxDEGajsBlG2gKpdy6T2F7KgH6U5l"
    "3gbxIsmbD452jTHX/XkNmL8upp3/v9zdoqKEwwQdAMjhyflCBoP8pZD1W8usVX98XnY3z4U7AHJ41EMPtudk0WkHWyHBUL8Ptm3M"
    "IG8+kIzC/OCJB7W2/bP10y//EoJl4I66YWmtiqm31eZ+pcMLu6vRSD1z+zuys2EiFVRCPXz6YbMJNH3kGIY2sQScHpDugL3z7Rs4"
    "3HqaPnfJUgqW7eZY15BNmA4A3JojIQSQvxTW+8u/Iw9umUjF49MrjxPvLf1IwEoLQAWjIVtqT0+9eu8248yl14sJZz7O3Y2AZQ66"
    "amWIrVRuH9sCx7shu5uvUUGefxAijgZLkL8IIGGYq/74mLXm8XthuEHegkEvjXUAsOs35XYVCaUUiXYWwuHBP8zIOBZYqpiN7oC9"
    "/a/f4nDbHH325YvJX9yMSBtyfTc6AGhjTsuxFQQKFMNs3LnKbti2VJROVHqjf1T0jt037pxvvvHgTn3OVVeQv2SlCnzJrOdUYmbI"
    "Ax/m2gKQrxCyYWdVcvk3dnGkwyB/cf83Pdayv19Tx+kl63FyJkhb3SPThF4SoyGBBDjeDQIgKqffqp9z/f8gFQcnItCmLMhSKOfy"
    "53xfNpPQppy331j479Xmmw/cCTNxOaxUpuqjS//9yycckxBmVmZAudWTSMWdQ16xEQFmEhztACciABhkuNLuFk21Q1pgKwlYplq2"
    "e4LKTSJEbnMkS3WdmYC9e9VPyFc4Wpt83jfI5c9qXlEj5NC2QTwkQA4vZN1GWDXvgDsPjaFAaRXpThdbcQYo7QVhgqYzOTwSLA+/"
    "WZaA4WFoBqsHTo8IhwfCX9TK3U22tfEvj3DHoblwuAfRPgHYJrirAZyIgPLKoFXOhCifClFVrTwLTh/IcCrVSzIKjnWB2w7A3r8e"
    "3LQL8tBWsJkEBcvURH2sjtXn/UnV29UEUT7lCcdn/vNaMeY0cKi5T0syRCmpGuKcCCmHncNbJ4rH1ZHhAqci6LFPMu16cAeO7CFs"
    "A46AEjekta9IRcFWChACds3bv5Lt9afnvGkVSkssW3aBDBe06RdBm3YBtEnnQFTOyKoKAwCSEdg178Le+wGsDX+GrNsM8heC8srT"
    "8ZEBiGHVwShYCvvglqXme7+3nYt/8nnyBJWOuQ/TOAzOxfTO1zbBibD6mYrisJNPApbj8L+BXj1EV0qSaLuyrQ435N7359t71jzG"
    "ZrKSPHmZp8uiGcr+c9t+gCWMM5dAn38DtKnnD+6xnD5oMxdCm7kQxsXfgvXeI7BWL4Ndux6iuApwBZRzsz8wA6RB5FfC+vCFz8Fw"
    "1bquu+/7LC0gGTvmSBmCySKQ0wu75h3YNe+CU3GIsolQI+QoQjSHEqVlhnzGs2sllTnRHYDQIZt33yxr3r6PGSC3P3vzIDSl62re"
    "Ba1qNowrfgh91qW5P9NAMBNIPfdDmG8+oNwoJRNUhxoIRIBlQrYfgPOqHy82Fn7nadmy9+8fo2TCRyGU417DU8UtuKNebTBJgNw+"
    "kO7yWVtee1g21iwll09NuNlurIQOjnWC2+vhuPhmOK695/itzAwXHIvvgnb6IqT+cCPsuo0QFTMAyP47D6fV+oESpF69909UNnGs"
    "KJ9axx0HVWfKoGRC7+VQOnYhxDD4odKNE7qql1i9uHAbIDSVKyIEKL8CHGmvNtc+tVU21Swlb35ae5UDGeFWcHcTnP/8EBzX3Xf8"
    "yOgFbcI8uG9fBW3GQshDW6CsQRayI08eYMZgPv+jZ7i9Tpn3aLta/UU7APSeQzJ1kqFMCFHPkpBtU7FsJdXPY72wTA8hAii9lEzF"
    "AM0BJKKAK6hsLjPg8AIuH2TD9hvsbW/8DmwrIRwP0NN6gwQ41gEOt8J909PQqj+b3XUAusIJrK05hJr6doQTJiyWcBs6Kor8mDe5"
    "AuPL8weuxOGB+zsvI/GLRbA2vAAxZubAc4q0VWj40JY5ds3bNxmfuvF+2bL3iAGQJoTA0U7YW1eo5Z2mFITk8gK6E3D5QZoOuPPU"
    "/2m6+ulwK9d9ZpNF2mGRGQmVteQrxOHeQ0ow7fTCrnn317Jhx9fIcAGO7NboPSAC7BS49SBcNy7LmozH3tyCR17bhE37W9DS2AnE"
    "U4dfBjOgCbhKgpgyKh+fPnMi/u3qeSgO9r/Kc33zecTvmg+572+g8lMH9lgQAH8JrNWP/lKbfO7DlF+R4Eg7Mu8oPalvB4dbYK5e"
    "rjY1iRDgDgLJCFhKCF8hYCVBeaMAhzstjbFA+ZWQtWvBXY3KPDkzE7da6nK4TSkQ7RQorwKcioF0R5W1etmTsqtxLrn8gDYITa3Q"
    "Ies3w3HJt+C49t4Bi7+2bh9ue+h1rF+/D9AIyPfB43FCE0eaGQYQS5iQoRjQHUPeuFLcfOVc3HH9J/utn8OtiN2mltTkLx64c5GA"
    "bNkLx6du/Kmx6PZbuF3FUsSYWb0IibTBWvdsj0Ic7gCQiICtlBoFySigaeB03ByJKChvFPjQVlB+OUBpn03mITVDEeIOAkKDqJwO"
    "e+NLi+w9q5ZzIuwnT3qjlStIgNvrIEonwP3fGwYsfscf38YPH3gFYMA7pggaEbI5RY80gVB7GGjsxIILZ+GJO5eixN/3BtVa+xQS"
    "v7oGYsw0ZBMa5UQI5PInnYvvDsDlTyERhla9KAvVSWYu0XTA4VHSS5dfCRlcvrRA2e4lOOjV6zITmdBgrX/uJ/a2Fc+zmfCTtzCL"
    "RvcBaYFTUTiu+8WARb/yy5fww7uehSgKIDiuBALIigwAYFsikO+Df9povPXXrTjt+gewvzXUZ3l97hLo864Gt+7LYmHBIHcQ3FHv"
    "tDY8/21ACTKA4ywDUoLpWLm96cXX7M0v3wKnD+QK5DZfHFEhgdvroM/6tMpo7Qfff+w9PPzrFXBPLoff44S0c78nMwOSEZhaicZ9"
    "zTj/239A0upbiO247D/A0hp4cgfSkUcfZFPNzbAtwFcA4HgQwqwmfF8huKthgbnmsW2yvf4iCpahxxU9hLrZTMJY8LV+i63d1YA7"
    "73kB2rhSGA4dcogBNLZs+CeVY9/f9uCbD7/ZZzkx9nToMy8FdzVkVS95guD2ulK5f111ZjEwvISwVJO+wwO5b+2t1tYVf0Uylqcc"
    "c8BQA1kcaYd2yjxoMxf2W+6bD70JgOHzucByeIJnZEsYp5ThN4++i021LX2W02ZdCo6GstvLCQ2ciEA277mOnF71p2FpLZBWZBSA"
    "hO60NvzlKWvLirvJcAHDmMfHkXaIsaf3W2btrgaseb8GztFFkMMokmYAHrcTCMVxzzNr+iynTZgHChbjcCiiv0pZHX7Q2fCJTGcd"
    "OiHMatftLwS3H5hj/e1PW2TznsXkCaa1sMMZ3mVoY2b1W+L3KzYD0SSchtZvucFASgkU+bFyaz3sPkaeGD0TonJG1idTkNMDDrdO"
    "5bY6BzBUQlhlO8EVgGzY/nVz/Z//JrsaJyoZaY6BnYFgmyBv4YAjZNX2eiDgHjZTdTScATfqa1uwesfBPsuI/Mqs0rsBKLF4uDUo"
    "m3edBQyFEGaVsK+7YG974yFry4oHSHeovx0PMbJlql2+r7DPIknTRmckATiPn8/UEAJIpLCvsbPPMlQ4RrmbskF6qyDb6ycDg4qH"
    "qJ5H/kJwpH2ivemlxzjSPofcgcHturO9K9sqtGo4+yyTSFlImfbAWVNDaQdYxdKsvjsdBUtzSvJhKwHSjVFAroRIG3AFIApGw970"
    "0lV27brHONblIF9B2umYCxlpgUHWnmVOl+37ZbudOpwO/bhmPFFao+zQ+5mjqJeCM5s6HR5wd/NYIBeTlV5FQZqwNr9yr7X5laeR"
    "ijrIX5QbEZlYc7RLhXGzFk1ryttsJfss4tA1FAc8QHzwysGBkLRswOvC1DFFfZbhUMuRcY6BwAxORIqArAhJCxA8QcC2Kqy1T79t"
    "b3rpW+QvUmqVXFKISaiEmlgX9BkX/0gUj/8DkpHsLtUMcCI04Opl/vTRQCgOEkON6RwbZncM48aX4IxJo/osw237laIlS3BXI0TF"
    "tDxgIEJYApoBCpSAW/ddaK5evpNDLedSoORwzCNbCAFOhMGpOPTqy76hn/35/4LTV8SpLHNf0t5jWb+532JfungWkOdBIjn8o4Q0"
    "AbSHcf6Msf2Wk50NOWUUULAMsmF7COiPEGbA6QXpTsi9H/zA2vrGCk5GfOTNBG9yMVNCeX5JJI35/3yZNnb2g6lnboM8tHX24foG"
    "rASQNuy6/kV9M6pK8Kn5U5Cqa4fQhm9yJwJi4QRQGMAti8/qs5w8tA3y4BYcFmhkAU0HNKMNOCYh6fw6bwGIhNPe+voz1o637iCn"
    "ZxCn5yizwd1NoEDZHuPcG2aI0okvmquXwd6/XsC29eyHNoM8+eC6jQOWvP+rFwJOA92dUYhhMl2SCNbeJtx6wwKc0k9EUe55H9zZ"
    "3O9q8GhwPARRMv4AcDQhrGLf5C0Et+w7y1r/3A7ZUX8luQex6yYCpAmOtEFUTH/ZWPCV0+AO7pYHt0BUzYFxyXclBUsaEe/bpf13"
    "VQaKYde8B3v3qn7LTR1ThPtuvwo41IFYLDVkUkgTiOw4hOoLZuLuL5zXb1lr00sgbw6KGQDQDUAzGoHehLAEGS51zMSBD79t/u2p"
    "1TLSNo68BT0pYdk/gVBKwEQE2oSz7tBnX/Fp6M4oIu2g/HJoVbOhT5oP8pfsZDOH/Emhg1nCfP3+AYvefNls/NdtV8Lc06RGip67"
    "+SJBsJkR2nwAs+ZNwtv3Xt9vebl/PayNL4DyK7O/CUuAAVE6cSeQ2YeQUDtsIWBvevER+9C268npy00BkoHQ1OmdJKCf/tkvUPH4"
    "ZZwMg8BgIVRgxjaVK8TlPZBT/Swhiqpgrf8z5IENA7pR/vtz81EccOOme15Ad00DnGNL4HJokAO4VYgITECoqQvojuGqJWdj+R2L"
    "4RpgTkq9eBeoRy+c5XNZKVCwNMy2+T6QGSFsA1LC3r3qBbt23fXkychxctnopaWl3Y0gh7vFuOjmeWLCvGUcbU97PgmioFIJI3QD"
    "5PSA8sp35HADBcMJCIHUE9/Nqvg3LpuDjb//Oi64YCaSbSF072lCuDuGeMo6wkEomZG0bISjSYQOtSO8uwnjKgvx4I+W4ukfXjMg"
    "Gda6Z2GteRZUPCGnTsypOIS/aBsFy5JAZoRIG+Y7v7vNPrDxM6IwnSuY83xhg0NtEGWTVulnXnMFFVW1cmON2qfo6U0dfD3rc7ZS"
    "oMLRL8MdVOq/bCd3aUOUngJr21swX/4ZjEu/N+Als8aV4PWffwFvfViLh1/agFXbD6KuIwKrMwokUirv3aEDPhfygx5Mm1KBaz85"
    "DV9dNAdaFp4EjnYgtfwmUEFpjuad1AE6BWNWi8IxADJJn7XrCuxtb9xJvoLcvbQkADOuVgqjZzyqz13yeXJ6wZ2ZqBmpk+FGTQIV"
    "jk1rswAIgphyfpO2Y+V79vY3z6G8CmS9lGaGKB2H5FP/DlFVDW3qBVldtqB6HBZUj0MqZWF3Qyf2N3dhb1MXTMtGWb4PUyoLMaYk"
    "gKI8b/bPDyDxqysgI20Qo6ZkJy3NQNogtx9UNHYZdzcDyKS07XzrRg61gApG56iPEuBkGLAl9OpF3xWjZ97DqZgyUYa7pwxYAlIq"
    "5aKVRDo5BEQaRPG4h23gHOTi/mFWqQT+EiTuvxqub70AbdL8rJvtcOiYVlWMaVXF2T9rH0j86grYO96BGDMjNzIAcCIEUTT2oKiY"
    "tjEzCAQAyI6Dn4PTmxsZQlObPWmnjPlfvFSbev49nAinz97tZW8zJ4/GusEte8EdB9XpPR0HIes3g4KjnqFgmYlsd+wZSFvpxISO"
    "xM8vgbXh+dyuHypSMcTvWQhr3XMQo6fn7tAkASTC0MadcZ8oHJuW3fbkqR+oIn9RdnmCRKq3dx6CKKraq8285BJRNmkPh1rSI8N1"
    "RHFOhCFGnQox/kx1FvxRw0ArHBuVTTt/b773x6+Iskm5+cZsE1RQAe5uRuKBq+G4/A44Ft2e/fWDhDywAYnf3gBZv1mNjJxTwkml"
    "vRWMjmuzPvO/IFKrXKRHiMiv2MXhNgwoGE7L6jnSDlE+5Tnjom/OovzKPdx5SJmRY02ALCE8eSBfvtJzuQK9Pn5Ac0Cfc9WPRaBE"
    "nQCXK2wLFCiBKKhE6pnvI/GLyyD3r8+9nmzAEqkX70L8ZxeDm3dDjJ6hOlCuMSAiINoJbdL8+ylYkpBdDeB0hFERUjH1fnXM6gCH"
    "wySjSvlx6rn36md//gpoerQ/VzOnw64QGmTjLpVedsSnUe0nCqvqtFM/+UvZ3ZSb2zoDaQNOH0TlNFibX0H85xcj9dStkIe25l7X"
    "sZCKwVq1DPG7z0PqyduUsqb0lMFlHhOBY52gQAn0uUt+AKGB3Hk9I4SYGfaOlTD/8qMNdu26anWGbS9PLpFKrom0gbz5tjbz0i+K"
    "8inLORkDOd3gcLvK5xA6ON4F6M503rYT3HkQ5ApAjJkFTsX6aCGD3HmAmXAkH7u5nWNdvh4l/GAgdCARhmyrBeWNgj5jIbQpn4Q2"
    "7UJQsCz7eqwU7D3vw972Buytr8GuXadCyAWVuan0jwYRZGstHOf/65f1sz//W9leh8x2UD/t04czqOwdbwWtd//vSY52XsxWUkWx"
    "zJQSWbsDEMXjntWmX/QfVDxul2zYAZAG8heAQ619E9KyG6JyJrTTLuvJfzgmmCFKxsNa+dDixPJ/e0oUVQ1upPSG0IBkDLKjHgBD"
    "FI+HGD0T2vgzQPkVKv3BFVBKfvDhpM+uJsiGbZC16yAbd4JjXaBAqRJR55L02UebZMteaJPmr3V9ddmZiHWDU/GemUJUzkifdRLp"
    "AIi69RmXXCJDLRdx56HLZaS9Srh8CSoYvYaE9oo26Zwt0Axwd7Pa2Ytsor9CLQAi7eBY36IAMCAPboOYufBP+vQLn7K2/3WJKJ6g"
    "7jNYSBswnBBlE1VELhmFveVVWOv/rM4p0R1qAUKaaoCVApuJnmMAyZuniMjPjIghhoVJALEukMMD4/x/vRJCg0yE1XFUvTju8WUh"
    "FVdmJVC2QiubtAK160Hlk6GVT4O9d40izen5e0F1fzBcyJxTNZAshqUNCpTCuOjmpbJp11nc3Tia8kYN/VDjdI8mp1fFd9Qf1d97"
    "101CvZyj59HhUNAQAVYSsrMBzsV3L9WmXnBINtao+eSo1Zl+xEXprCcmqKNX05P44QO6cnBjS3UeLgoqVLpCIotQLUtQ5Ux2XHnn"
    "2aknvlOHWDchl+TPrJE+tWEYA1j9QtrgUCuMc2+4S5933ZPcth89w+KoRzt+Aia2AIdLDX1N/7v9SR8XAZF26NWXHeTWfQtSL/90"
    "pTItQzgQ7USDJTjaAW38nOXGpd+7DQKANEH6sX13x7eLZMxCJi9xwI+KVnK0E8gb9baomHYerGT6hOrhl4YeVxCpXJZoByhv1O+p"
    "avY/qS9Hi/WrtBmZx8SyBOIhkOF6R0yavwCuoJmztOZEIjMnx8PQJp37G61yxg2Ih9T3bQ3gPR6ZhKTBkQ6IUaeuNM794mnkL67l"
    "7kbkctTRCQEJlTdvJWFUL7rVOHPJ1zgVV07VLNo9ogkBETjcCpFfud248KbponTii5yMqHOARxop6UURh1pATm+HXr3oUnHquf/D"
    "sa50e7N71SObEECREu0EkRbT515zmTbxnJshbeZIRx8HKX/kDQRA4Fg3ONIGbdzs5xyX3jJZFI17hbuaVIpbDm0c+YQAvUQTYYji"
    "Cb/UZlw0QRsz61mYSSAePkFmLL2jSUWVW8lfvE0/4+pr9DMWX0HuQJvKPT9cLluc+C8FyxaZMHGsC3D6arXqy64SY6s/YW97806O"
    "tH2SraRSxzvcH8kSmRMhlavvzmvSJp/3UzF+zn1gBkfb1R5skEd8fHwIyYBIbVhjIYj8ylU88ewFsFJny8adX+fupus41n3YNZKD"
    "vnaAm6rlu5VUp84RQeRXbhRlk38jyic/Am9BArap/Hpu/5BG68ePEKBH7s+xLrV68Ras1ifPXw1P3vftHW8t5FDLYk6Ez+NYt5pn"
    "dOdheQ6Jo6xIr6M1egQKat/EVvqLi4lBugvwBOu0kgnPUKDkJcqveJOcPkVQuB3kcA16VPTGx5OQDDIvMBkBkwCVnrJPlJ7yIMqn"
    "PIhUfLzsOHgBSFRzqGkqx7rnwkq5OBUH9XxTA/c4F1naIKGpI/00QzkmA/m74A58CBJbRNkpq8hXvJIMN2C4wJFWsJ1STlYavv3R"
    "x5uQHqR7eTIGjnUrobPDs0+rnP4QBUshOxsBaZ0qOw5WQdNLEesqYjMRJKG5OR7SoBksvPlJjrSHteLxnTCTTXB5D1HB6O0wY1Ek"
    "k6BgMVhKcKxDnWbEEsDwb1Qp26MmTuKjwcdj2fsPhJOEjDCcJGSE4SQhIwwnCRlh+H/+fF6oKqbjZgAAAABJRU5ErkJggg=="
)


def get_photo(size):
    """PhotoImage ikon Blender berukuran size x size, atau None kalau gagal dibuat."""
    try:
        from PIL import Image, ImageTk
        img = Image.open(io.BytesIO(base64.b64decode(_DATA))).convert("RGBA")
        resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
        try:
            small = img.convert("RGBa").resize((size, size), resample).convert("RGBA")
        except Exception:   # Pillow tanpa mode RGBa: pengecilan biasa
            small = img.resize((size, size), resample)
        return ImageTk.PhotoImage(small)
    except Exception as exc:
        C.log(f"Ikon Blender gagal dibuat: {exc!r}")
        return None
