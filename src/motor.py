from scipy.stats import poisson

class MotorPreditivo:
    def __init__(self, media_gols_liga=2.65):
        self.media_gols_liga = media_gols_liga

    def calcular_forcas(self, gc, sc, gf, sf):
        ataque_casa = gc / self.media_gols_liga
        ataque_fora = gf / self.media_gols_liga
        defesa_casa = sc / self.media_gols_liga
        defesa_fora = sf / self.media_gols_liga
        
        vantagem_casa = 1.20 
        xg_casa = ataque_casa * defesa_fora * self.media_gols_liga * vantagem_casa
        xg_fora = ataque_fora * defesa_casa * self.media_gols_liga * (1 / vantagem_casa)
        return xg_casa, xg_fora

    def probabilidade_over_15(self, xg_casa, xg_fora):
        prob_casa = [poisson.pmf(i, xg_casa) for i in range(10)]
        prob_fora = [poisson.pmf(i, xg_fora) for i in range(10)]
        
        prob_under_15 = sum(prob_casa[i] * prob_fora[j] for i in range(10) for j in range(10) if i + j < 2)
        return 1.0 - prob_under_15

    def criterio_kelly(self, prob_real, odd_casa):
        b = odd_casa - 1
        p = prob_real
        q = 1 - p
        kelly = (p * b - q) / b
        kelly_ajustado = kelly * 0.50 # Meio Kelly
        
        if kelly_ajustado <= 0: return 0.0
        if kelly_ajustado > 0.05: return 0.05 # Limite de 5%
        return kelly_ajustado
