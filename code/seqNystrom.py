from os import environ
environ['OMP_NUM_THREADS'] = '1'
import numpy as np
import math
import time
from scipy.linalg import norm, cholesky, qr, svd, solve_triangular
from data_generation import *
from utility import *

def SRHT_sketch(n, l, random_seed):
	rng = np.random.default_rng(random_seed)
	
	signs = rng.choice([-1, 1], size=n)
	randCol = rng.choice(n, l, replace=False)
	
	return np.fromfunction(np.vectorize(lambda i, j: signs[i]*(-1)**(bin(i & randCol[j]).count("1"))), (n, l), dtype=int) / math.sqrt(l)

def short_axis_sketch(n, l, t, random_seed):
	rng = np.random.default_rng(random_seed)
	
	sketch = np.zeros((n,l), dtype='d')
	bounds = np.ceil(np.linspace(0,l,t+1))
	for i in range(n):
		 col = rng.integers(bounds[:t], bounds[1:], size=t)
		 sketch[i,col] = rng.choice([-1, 1], size=t)*rng.uniform(1., 2., size=t)
	return sketch

def block_gaussian_sketch(n, l, random_seed):
	rng = np.random.default_rng(random_seed)
	return rng.normal(size = (n, l))

def block_SRHT(n, l, random_seed):
	col_rng = np.random.default_rng(random_seed)
	
	randCol = col_rng.choice(n, l, replace=False)
	signsRows = col_rng.choice([-1, 1], size=n)
	signsCols = col_rng.choice([-1, 1], size=l)
	
	return np.fromfunction(np.vectorize(lambda i, j: signsRows[i]*signsCols[j]*(-1)**(bin(i & randCol[j]).count("1"))), (n, l), dtype=int) / math.sqrt(l)

#======== getting setting from csv file ========
save_results = False
line_id = get_counter()
n, matrix_type, RR, p, sigma, l, k, sketch_matrix, t = get_settings_from_csv(line_id)
print_settings(n, matrix_type, RR, p, sigma, l, k, sketch_matrix, t, 1)

#======== checking assumptions ========
assert n > 0 and math.log2(n).is_integer(), "n must be a power of 2"
assert l >= k, "l must be greater or equal than k"
assert t <= l, "t must be smaller or equal than l"

#======== generating A ========
match matrix_type:
	case 0:
		A = A_PolyDecay(n, RR, p)
	case 1:
		A = A_ExpDecay(n, RR, p)
	case 2:
		A = A_MNIST(n, sigma)
	case 3:
		A = A_YearPredictionMSD(n, sigma)
	case _:
		raise Exception("Unknown matrix type")

wt = time.time()

#======== generating omega ========
random_seed = np.random.randint(2**30)
match sketch_matrix:
	case 0:
		omega = SRHT_sketch(n, l, random_seed)
	case 1:
		omega = short_axis_sketch(n, l, t, random_seed)
	case 2:
		omega = block_gaussian(n, l, random_seed)
	case 3:
		omega = block_SRHT(n, l, random_seed)
	case _:
		raise Exception("Unknown sketch type")

#======== multiplications to obtain C and B ========
C = A @ omega
B = omega.T @ C

#======== cholesky factorization and calculation of Z ========
cholesky_success = True
try:
	L = cholesky(B).T
	Z = solve_triangular(L, C.T, lower=True).T
except np.linalg.LinAlgError:
	cholesky_success = False
	B_U, B_S, B_Vt = svd(B, full_matrices=False)
	pseudo_sqrtS = np.array([1./b_s**0.5 if b_s != 0 else 0 for b_s in B_S])
	Z = C @ B_U @ np.diag(pseudo_sqrtS) @ B_U.T

#======== QR factorization ========
Q, R = qr(Z, mode='economic')

#======== truncated SVD ========
U, S, Vt = svd(R, full_matrices=False)
U_k = U[:,:k]
S_k = S[:k]

#======== computation of Q*U_k ========
Uhat_k = Q @ U_k

#======== computation and saving of results ========
wt = time.time() - wt
print("lowrank approximation completed")

# We keep the following multiplication outside the runtime because it is only needed for computing the trace error
A_nystrom = Uhat_k @ np.diag(S_k**2) @ Uhat_k.T

error_nuc = np.linalg.norm(A - A_nystrom, ord='nuc')/nuc_norm_A(matrix_type, n, RR, p, sigma)
if save_results:
	save_results_to_csv(line_id, 1, cholesky_success, random_seed, error_nuc, wt)
	add_counter(1)
print_results(error_nuc, wt, cholesky_success, random_seed)
