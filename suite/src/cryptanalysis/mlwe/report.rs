//! Every attack, every parameter set, every cost model — as one table.
//!
//! The point of collecting them is that no single number means anything on its
//! own. "ML-KEM-512 has 118-bit security" is only true in the core-SVP model
//! against the primal attack; the same parameter set is at 151 bits in a
//! gate-count model and somewhere else again under a dual attack whose
//! diagnostics fire. A table makes the spread visible, which is the honest
//! presentation.
//!
//! Rows carry a `note` field, and where a dual estimate lands in the
//! Ducas–Pulles contradictory regime the note says so. A row with that note is
//! not a security claim.

use super::cost::{BkzModel, Reps, SvpModel};
use super::dual::{dual_distinguish, dual_matzov, dual_matzov_consistent, DualSearch};
use super::hybrid::best_hybrid;
use super::params::{all_lwe, all_sis, LweInstance};
use super::primal::{primal_usvp_2016, sis_estimate};

/// One line of the report.
#[derive(Clone, Debug, PartialEq)]
pub struct AttackRow {
    pub instance: String,
    pub attack: String,
    pub model: String,
    pub beta: f64,
    pub log2_cost: f64,
    pub log2_memory: f64,
    /// Anything the reader needs in order not to misread the cost.
    pub note: String,
}

/// A search configuration tuned for reports: coarse enough to be fast, fine
/// enough that the optima do not move by more than a bit.
pub fn report_search() -> DualSearch {
    DualSearch {
        beta_step: 16,
        k_fft_max: 32,
        k_enum_max: 16,
        ..Default::default()
    }
}

/// Every attack this module implements, against one instance, in one model.
pub fn rows_for(inst: &LweInstance, model: &BkzModel) -> Vec<AttackRow> {
    let search = report_search();
    let mut rows = Vec::new();

    if let Some(e) = primal_usvp_2016(inst, model) {
        rows.push(AttackRow {
            instance: inst.name.clone(),
            attack: "primal-usvp".into(),
            model: model.label(),
            beta: e.beta,
            log2_cost: e.log2_cost,
            log2_memory: e.log2_memory,
            note: format!("d = {}, using {} of {} samples", e.d, e.m_used, inst.m),
        });
    }
    if let Some(e) = best_hybrid(inst, model, 512) {
        rows.push(AttackRow {
            instance: inst.name.clone(),
            attack: e.method.into(),
            model: model.label(),
            beta: e.beta,
            log2_cost: e.log2_cost,
            log2_memory: e.log2_memory,
            note: format!("{} coordinates guessed", e.guessed),
        });
    }
    if let Some(e) = dual_distinguish(inst, model, &search) {
        rows.push(AttackRow {
            instance: inst.name.clone(),
            attack: "dual-distinguish".into(),
            model: model.label(),
            beta: e.beta,
            log2_cost: e.log2_cost,
            log2_memory: e.log2_memory,
            note: format!(
                "ε = 2^{:.1}, {:.1} samples; {}",
                e.log2_advantage,
                e.log2_samples,
                e.diagnostics.verdict()
            ),
        });
    }
    if let Some(e) = dual_matzov(inst, model, &search) {
        rows.push(AttackRow {
            instance: inst.name.clone(),
            attack: "dual-matzov (unfiltered)".into(),
            model: model.label(),
            beta: e.beta,
            log2_cost: e.log2_cost,
            log2_memory: e.log2_memory,
            note: format!(
                "k_lat/k_fft/k_enum = {}/{}/{}, p = {}; {}",
                e.k_lat,
                e.k_fft,
                e.k_enum,
                e.p,
                e.diagnostics.verdict()
            ),
        });
    }
    if let Some(e) = dual_matzov_consistent(inst, model, &search) {
        rows.push(AttackRow {
            instance: inst.name.clone(),
            attack: "dual-matzov (consistent)".into(),
            model: model.label(),
            beta: e.beta,
            log2_cost: e.log2_cost,
            log2_memory: e.log2_memory,
            note: format!(
                "k_lat/k_fft/k_enum = {}/{}/{}, p = {}; {}",
                e.k_lat,
                e.k_fft,
                e.k_enum,
                e.p,
                e.diagnostics.verdict()
            ),
        });
    }
    rows
}

/// The cheapest *believable* attack on an instance: the minimum over all rows
/// whose note does not flag the contradictory regime.
pub fn best_believable(inst: &LweInstance, model: &BkzModel) -> Option<AttackRow> {
    rows_for(inst, model)
        .into_iter()
        .filter(|r| !r.note.contains("contradictory") && !r.note.contains("not an attack"))
        .min_by(|a, b| a.log2_cost.total_cmp(&b.log2_cost))
}

/// The whole table: every standardised LWE instance, every model given.
pub fn full_report(models: &[BkzModel]) -> Vec<AttackRow> {
    let mut rows = Vec::new();
    for inst in all_lwe() {
        for m in models {
            rows.extend(rows_for(&inst, m));
        }
    }
    for sis in all_sis() {
        for m in models {
            if let Some(e) = sis_estimate(&sis, m) {
                rows.push(AttackRow {
                    instance: sis.name.clone(),
                    attack: "sis-forgery".into(),
                    model: m.label(),
                    beta: e.beta,
                    log2_cost: e.log2_cost,
                    log2_memory: e.log2_memory,
                    note: format!(
                        "m = {}; a short SIS solution is not yet a signature — see primal.rs",
                        e.m_used
                    ),
                });
            }
        }
    }
    rows
}

/// Render rows as a fixed-width table.
pub fn render_table(rows: &[AttackRow]) -> String {
    let mut out = String::new();
    let w_inst = rows
        .iter()
        .map(|r| r.instance.len())
        .max()
        .unwrap_or(8)
        .max(8);
    let w_atk = rows
        .iter()
        .map(|r| r.attack.len())
        .max()
        .unwrap_or(6)
        .max(6);
    let w_mod = rows.iter().map(|r| r.model.len()).max().unwrap_or(5).max(5);
    out.push_str(&format!(
        "{:<w_inst$}  {:<w_atk$}  {:<w_mod$}  {:>6}  {:>9}  {:>7}  {}\n",
        "instance", "attack", "model", "beta", "log2 cost", "log2 mem", "notes",
    ));
    out.push_str(&format!("{}\n", "-".repeat(w_inst + w_atk + w_mod + 40)));
    for r in rows {
        out.push_str(&format!(
            "{:<w_inst$}  {:<w_atk$}  {:<w_mod$}  {:>6.0}  {:>9.1}  {:>7.1}  {}\n",
            r.instance, r.attack, r.model, r.beta, r.log2_cost, r.log2_memory, r.note,
        ));
    }
    out
}

/// A margin table: cheapest believable attack against the NIST floor.
///
/// Two columns, because one would be a claim the models do not support.
///
/// * **gates + tours** — `2^{0.292β + 16.4}` per sieve call, eight BKZ tours.
///   This is the convention of the round-3 Kyber and Dilithium documents, and
///   the one whose numbers are comparable to NIST's gate-count floors.
/// * **+ d4f** — the same, minus Ducas' dimensions for free.
///
/// The second column is the more attacker-friendly and the less trustworthy,
/// and the reason is worth stating rather than burying: the `+16.4` constant was
/// measured for a sieve implementation that already exploits dimensions for
/// free, so subtracting `d4f` from the block size on top of it plausibly
/// double-counts the same saving. A negative margin in that column is a
/// statement about stacked cost models, not a break. The first column is the
/// one to quote.
///
/// Rows exclude any dual estimate whose diagnostics fire.
pub fn margin_table() -> String {
    let gates = BkzModel {
        svp: SvpModel::GateCount,
        reps: Reps::Tours(8),
        d4f: false,
    };
    let with_d4f = BkzModel::gate_count_realistic();
    debug_assert!(matches!(gates.svp, SvpModel::GateCount));

    let mut out = String::new();
    out.push_str(&format!(
        "{:<34}  {:>4}  {:>10}  {:>10}  {:>8}  {:>8}  {}\n",
        "instance", "cat", "NIST floor", "gates+tour", "margin", "+d4f", "cheapest attack"
    ));
    out.push_str(&format!("{}\n", "-".repeat(120)));
    for inst in all_lwe() {
        let (Some(a), Some(b)) = (
            best_believable(&inst, &gates),
            best_believable(&inst, &with_d4f),
        ) else {
            continue;
        };
        let Some(cat) = inst.category else { continue };
        let floor = cat.gate_floor_bits();
        out.push_str(&format!(
            "{:<34}  {:>4}  {:>10.1}  {:>10.1}  {:>+8.1}  {:>+8.1}  {}\n",
            inst.name,
            cat.number(),
            floor,
            a.log2_cost,
            a.log2_cost - floor,
            b.log2_cost - floor,
            a.attack,
        ));
    }
    out.push_str(
        "\n`gates+tour` is 2^(0.292b + 16.4) per sieve call with 8 BKZ tours — the convention\n\
         whose numbers are comparable to NIST's floors, and the column to quote. `+d4f` also\n\
         subtracts dimensions for free, which plausibly double-counts a saving the +16.4 constant\n\
         already includes: read a negative there as a statement about stacked models, not a break.\n\
         Rows exclude any dual estimate flagged as Ducas-Pulles contradictory.\n\
         \n\
         Note: ML-KEM-512 coming out under its floor in the quotable column is the known result,\n\
         not a surprise. MATZOV-style dual attacks have put it a few bits below category 1 since\n\
         2022, and it is why deployment guidance points at ML-KEM-768.\n",
    );
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_instance_produces_rows_in_every_model() {
        for model in [
            BkzModel::core_svp_classical(),
            BkzModel::core_svp_quantum(),
            BkzModel::gate_count_realistic(),
        ] {
            for inst in all_lwe() {
                let rows = rows_for(&inst, &model);
                assert!(rows.len() >= 4, "{} in {}", inst.name, model.label());
                for r in &rows {
                    assert_eq!(r.model, model.label());
                    assert!(r.log2_cost.is_finite() && r.log2_cost > 0.0);
                    assert!(r.beta >= 50.0);
                }
            }
        }
    }

    #[test]
    fn the_believable_best_is_never_a_flagged_row() {
        let model = BkzModel::gate_count_realistic();
        for inst in all_lwe() {
            let b = best_believable(&inst, &model).unwrap();
            assert!(!b.note.contains("contradictory"), "{}", inst.name);
        }
    }

    #[test]
    fn filtering_never_makes_the_answer_cheaper() {
        let model = BkzModel::core_svp_classical();
        for inst in all_lwe() {
            let all_min = rows_for(&inst, &model)
                .into_iter()
                .map(|r| r.log2_cost)
                .fold(f64::INFINITY, f64::min);
            let believable = best_believable(&inst, &model).unwrap().log2_cost;
            assert!(believable >= all_min - 1e-9);
        }
    }

    #[test]
    fn the_report_orders_the_parameter_sets() {
        let model = BkzModel::gate_count_realistic();
        let cost = |i: &LweInstance| best_believable(i, &model).unwrap().log2_cost;
        let sets = all_lwe();
        assert!(cost(&sets[0]) < cost(&sets[1])); // ML-KEM 512 < 768
        assert!(cost(&sets[1]) < cost(&sets[2])); // 768 < 1024
        assert!(cost(&sets[3]) < cost(&sets[4])); // ML-DSA 44 < 65
        assert!(cost(&sets[4]) < cost(&sets[5])); // 65 < 87
    }

    #[test]
    fn tables_render_without_panicking_and_mention_the_model() {
        let rows = full_report(&[BkzModel::core_svp_classical()]);
        assert!(!rows.is_empty());
        let t = render_table(&rows);
        assert!(t.contains("primal-usvp"));
        assert!(t.contains("core-svp-classical"));
        assert!(t.lines().count() > rows.len());

        let m = margin_table();
        assert!(m.contains("ML-KEM-512"));
        assert!(m.contains("gates+tour"));
        assert!(m.contains("d4f"));
        assert!(m.contains("Ducas-Pulles"));
        // Both margin columns must be present for all six sets.
        assert_eq!(m.lines().filter(|l| l.starts_with("ML-")).count(), 6);
    }

    #[test]
    fn ml_kem_512_is_the_one_that_does_not_clear_its_floor() {
        // This reproduces the best-known live claim about these parameter sets
        // rather than contradicting it. In a gate-count model with BKZ tours,
        // the MATZOV-style dual attack puts ML-KEM-512 *below* its category-1
        // requirement; the published figure is about 3.5 bits and ours is
        // single-digit. Everything else clears its floor.
        //
        // If this test ever starts failing because 512 clears the floor, the
        // dual estimator has become less capable, not the scheme more secure.
        let model = BkzModel {
            svp: SvpModel::GateCount,
            reps: Reps::Tours(8),
            d4f: false,
        };
        let all = all_lwe();
        let kem512 = best_believable(&all[0], &model).unwrap();
        let floor = all[0].category.unwrap().gate_floor_bits();
        assert!(
            kem512.log2_cost < floor,
            "ML-KEM-512 cleared its floor at {:.1}",
            kem512.log2_cost
        );
        assert!(
            floor - kem512.log2_cost < 20.0,
            "ML-KEM-512 is {:.1} bits under its floor — too far to be the known result",
            floor - kem512.log2_cost
        );
        assert!(kem512.attack.contains("dual"), "via {}", kem512.attack);

        // The other five clear theirs.
        for inst in all.iter().skip(1) {
            let b = best_believable(inst, &model).unwrap();
            let floor = inst.category.unwrap().gate_floor_bits();
            assert!(
                b.log2_cost > floor,
                "{}: {:.1} below floor {:.1} via {}",
                inst.name,
                b.log2_cost,
                floor,
                b.attack
            );
        }
    }

    #[test]
    fn stacking_d4f_on_the_gate_model_lowers_every_margin() {
        // Not a break — see margin_table's doc comment on double counting — but
        // the direction must be consistent, and it is worth having a test that
        // fails if someone quietly makes d4f the default.
        let plain = BkzModel {
            svp: SvpModel::GateCount,
            reps: Reps::Tours(8),
            d4f: false,
        };
        let stacked = BkzModel::gate_count_realistic();
        for inst in all_lwe() {
            let a = best_believable(&inst, &plain).unwrap().log2_cost;
            let b = best_believable(&inst, &stacked).unwrap().log2_cost;
            assert!(b < a, "{}: d4f did not lower the cost", inst.name);
        }
    }

    #[test]
    fn margins_land_in_the_right_ballpark() {
        let model = BkzModel::gate_count_realistic();
        for inst in all_lwe() {
            let b = best_believable(&inst, &model).unwrap();
            let floor = inst.category.unwrap().gate_floor_bits();
            assert!(
                b.log2_cost > floor - 30.0,
                "{}: {:.1} against floor {:.1} — check the model before believing this",
                inst.name,
                b.log2_cost,
                floor
            );
        }
    }

    #[test]
    fn sis_rows_carry_the_caveat_that_forgery_is_not_lattice_bound() {
        let rows = full_report(&[BkzModel::core_svp_classical()]);
        let sis: Vec<_> = rows.iter().filter(|r| r.attack == "sis-forgery").collect();
        assert_eq!(sis.len(), 3);
        for r in sis {
            assert!(r.note.contains("not yet a signature"));
        }
    }
}
