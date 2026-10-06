py.install_sources(
  'BSD.py',
  'Qcurves.py',
  '__init__.py',
  'addition_formulas_ring.py',
  'all.py',
  'binary_batch.py',
  'binary_hardware.py',
  'binary_hardware_codec.pyx',
  'cardinality.py',
  'cm.py',
  'constructor.py',
  'descent_two_isogeny.pyx',
  'ec_database.py',
  'ell_curve_isogeny.py',
  'ell_egros.py',
  'ell_field.py',
  'ell_finite_field.py',
  'ell_generic.py',
  'ell_local_data.py',
  'ell_modular_symbols.py',
  'ell_number_field.py',
  'ell_padic_field.py',
  'ell_point.py',
  'ell_rational_field.py',
  'ell_tate_curve.py',
  'ell_torsion.py',
  'ell_wp.py',
  'formal_group.py',
  'gal_reps.py',
  'gal_reps_number_field.py',
  'gp_simon.py',
  'heegner.py',
  'height.py',
  'hom.py',
  'hom_composite.py',
  'hom_fractional.py',
  'hom_frobenius.py',
  'hom_scalar.py',
  'hom_sum.py',
  'hom_velusqrt.py',
  'homset.py',
  'isogeny_class.py',
  'isogeny_small_degree.py',
  'jacobian.py',
  'kodaira_symbol.py',
  'kraus.py',
  'lseries_ell.py',
  'mod5family.py',
  'mod_poly.py',
  'mod_sym_num.pyx',
  'modular_parametrization.py',
  'padic_lseries.py',
  'padics.py',
  'period_lattice.py',
  'period_lattice_region.pyx',
  'saturation.py',
  'sha_tate.py',
  'weierstrass_morphism.py',
  'weierstrass_transform.py',
  subdir: 'sage/schemes/elliptic_curves',
)

extension_data = {
  'descent_two_isogeny': files('descent_two_isogeny.pyx'),
  'mod_sym_num': files('mod_sym_num.pyx'),
  'period_lattice_region': files('period_lattice_region.pyx'),
}

foreach name, pyx : extension_data
  py.extension_module(
    name,
    sources: pyx,
    subdir: 'sage/schemes/elliptic_curves',
    install: true,
    include_directories: [inc_cpython, inc_flint, inc_rings],
    dependencies: [py_dep, cypari2, cysignals, flint, gmp, mpfr, numpy],
  )
endforeach

# Portable exact-word backend; Metal is an optional host-specific addition.
hardware_sources = files('binary_hardware_cpu.cpp')
hardware_deps = [dependency('threads')]
hardware_cpp_args = []
hardware_objcpp_args = []
if host_machine.system() == 'darwin'
  if add_languages('objcpp', required: false)
    metal_frameworks = dependency('appleframeworks', modules: ['Foundation', 'Metal'], required: false)
    if metal_frameworks.found()
      hardware_sources += files('binary_hardware_metal.mm')
      hardware_deps += [metal_frameworks]
      hardware_cpp_args += ['-DBH_WITH_METAL']
      hardware_objcpp_args += ['-DBH_WITH_METAL', '-fobjc-arc']
    endif
  endif
endif
shared_module(
  '_binary_hardware_native',
  hardware_sources,
  name_prefix: '',
  install: true,
  install_dir: py.get_install_dir() / 'sage/schemes/elliptic_curves',
  dependencies: hardware_deps,
  cpp_args: hardware_cpp_args,
  objcpp_args: hardware_objcpp_args,
)
if ntl.found()
  py.extension_module(
    'binary_hardware_codec',
    files('binary_hardware_codec.pyx'),
    subdir: 'sage/schemes/elliptic_curves',
    install: true,
    override_options: ['cython_language=cpp'],
    include_directories: [inc_cpython, inc_rings, inc_ntl],
    dependencies: [py_dep, ntl, gmp, cysignals],
  )
endif
