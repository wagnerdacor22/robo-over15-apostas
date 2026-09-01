import math


class MotorPreditivo:
    def __init__(self, media_gols_liga=2.65):
        self.media_gols_liga = media_gols_liga

    def calcular_forcas(self, gc, sc, gf, sf):
        """
        Estima gols esperados com forca relativa de ataque e defesa.

        gc/sc sao as medias do mandante em casa; gf/sf sao as medias do
        visitante fora. A versao anterior dividia cada media pela media TOTAL
        de gols da liga, reduzindo artificialmente o lambda e praticamente
        eliminando apostas de Over 1.5.
        """
        media_casa_liga = self.media_gols_liga * 0.55
        media_fora_liga = self.media_gols_liga * 0.45

        ataque_casa = gc / media_casa_liga
        defesa_fora = sf / media_casa_liga
        ataque_fora = gf / media_fora_liga
        defesa_casa = sc / media_fora_liga

        xg_casa = ataque_casa * defesa_fora * media_casa_liga
        xg_fora = ataque_fora * defesa_casa * media_fora_liga

        # Evita que amostras muito pequenas produzam lambdas absurdos.
        xg_casa = min(max(xg_casa, 0.15), 4.0)
        xg_fora = min(max(xg_fora, 0.15), 4.0)
        return xg_casa, xg_fora

    def probabilidade_over_15(self, xg_casa, xg_fora):
        # A soma de duas Poisson independentes tambem e Poisson.
        lamb = xg_casa + xg_fora
        prob_zero_ou_um = math.exp(-lamb) * (1.0 + lamb)
        return min(max(1.0 - prob_zero_ou_um, 0.0), 1.0)

    def criterio_kelly(self, prob_real, odd_casa):
        b = odd_casa - 1
        p = prob_real
        q = 1 - p
        kelly = (p * b - q) / b
        kelly_ajustado = kelly * 0.25  # Quarto de Kelly: menos volatilidade
        
        if kelly_ajustado <= 0: return 0.0
        if kelly_ajustado > 0.02: return 0.02 # Limite de 2% por selecao
        return kelly_ajustado
