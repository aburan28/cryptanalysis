# Untimed mathematical certificate for the two frozen n=83 subgroup orders.
# Run through /Volumes/SSD990/cryptanalysis/sage, the checked launcher.
r0 = ZZ(2417851639230796216685689)
r1 = ZZ(8569786107849059)
print("K0_r_prime", r0.is_prime(proof=True))
print("K1_r_prime", r1.is_prime(proof=True))
print("K0_group_order", 4*r0)
print("K1_group_order", 1128547018*r1)
