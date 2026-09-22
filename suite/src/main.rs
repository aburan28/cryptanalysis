//! `ca-suite` — the command line of the attack suite.
//!
//! One subcommand per tool: the auto-attack runner and its individual
//! attacks (`auto`, `boomerang`, `rectangle`, `sbox`), the hash attacks
//! (`hash-auto`, `length-extension`), the AES related-key study, the visual
//! demos, the research bench, the collaborative Pollard rho (`rho-collab`)
//! and the ML-KEM / ML-DSA cryptanalysis (`mlwe`).  `ca-suite --help` lists
//! them; every subcommand has its own `--help`.

mod cli_mlwe;

use clap::{Parser, Subcommand};
use cryptanalysis_suite::{
    ecc::point::Point,
    utils::encoding::{from_hex, to_hex},
};
use num_bigint::BigUint;

#[derive(Parser)]
#[command(
    name = "ca-suite",
    version,
    about = "Cryptanalysis suite: symmetric, hash, ECDLP, lattice and post-quantum attacks"
)]
struct Cli {
    /// Color output mode: `auto` (default), `always`, or `never`.
    /// `auto` enables colors only on a TTY.  Respected by every visual
    /// renderer.
    #[arg(long, global = true, default_value = "auto")]
    color: String,

    #[command(subcommand)]
    command: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// List all registered ciphers known to the auto-attack runner.
    ListCiphers,
    /// Run every applicable attack against a registered cipher and
    /// emit a Markdown report.
    ///
    /// Example: `ca-suite auto --cipher toyspn-2r`
    Auto {
        /// Cipher identifier (use `list-ciphers` to see options).
        #[arg(long)]
        cipher: String,
        /// Number of plaintext pairs for the boomerang.
        #[arg(long, default_value_t = 65_536)]
        boomerang_pairs: usize,
        /// Pool size for the rectangle attack.
        #[arg(long, default_value_t = 2048)]
        rectangle_pool: usize,
        /// Negative log₂ of the differential-trail probability
        /// threshold.  `12` here means threshold = `2⁻¹²`.
        #[arg(long, default_value_t = 12)]
        trail_threshold_neg_log2: u32,
        /// Max number of trails to render.
        #[arg(long, default_value_t = 5)]
        trail_top_k: usize,
    },
    /// Run just the boomerang distinguisher against a registered cipher.
    Boomerang {
        #[arg(long)]
        cipher: String,
        /// α and δ in hex (low byte first), e.g. `0100`.  Defaults to
        /// the cipher's canonical pair.
        #[arg(long)]
        alpha: Option<String>,
        #[arg(long)]
        delta: Option<String>,
        #[arg(long, default_value_t = 65_536)]
        pairs: usize,
    },
    /// Run just the rectangle attack against a registered cipher.
    Rectangle {
        #[arg(long)]
        cipher: String,
        #[arg(long)]
        alpha: Option<String>,
        #[arg(long)]
        delta: Option<String>,
        #[arg(long, default_value_t = 2048)]
        pool: usize,
    },
    /// Print the S-box differential / linear / boomerang report for a
    /// registered cipher.
    Sbox {
        #[arg(long)]
        cipher: String,
    },
    /// Run the full research bench and emit the Markdown report.
    /// (Equivalent to `cargo test --lib --release bench_demo --
    /// --ignored --nocapture`, but from the command line.)
    Bench,
    /// Auto-run every applicable hash-function attack (length
    /// extension, birthday collision, Joux multicollision,
    /// differential bias) against the named hash.  Targets: md4, md5, sha1.
    HashAuto {
        /// Hash identifier: `md4`, `md5`, or `sha1`.
        #[arg(long)]
        hash: String,
    },
    /// Length-extension attack demo against a Merkle-Damgård hash.
    LengthExtension {
        /// Hash identifier: `md4`, `md5`, or `sha1`.
        #[arg(long)]
        hash: String,
        /// Length (in bytes) of the unknown secret prefix.
        #[arg(long)]
        secret_len: usize,
        /// Original message body (hex-encoded).
        #[arg(long)]
        message_hex: String,
        /// Suffix to append (hex-encoded).
        #[arg(long)]
        suffix_hex: String,
        /// Digest of `secret || message_hex` (hex-encoded).
        #[arg(long)]
        digest_hex: String,
    },
    /// **AES related-key attack** — propagate a key-difference
    /// through the schedule + run avalanche + run a 4-round local
    /// collision demo.  Emits a Markdown report.
    AesRelatedKey {
        /// Key size in bits: 128 or 256.
        #[arg(long, default_value_t = 128)]
        key_bits: u32,
        /// Key-difference ΔK in hex (length = key_bits / 8 bytes).
        /// Defaults to a single-active-byte difference at position 0.
        #[arg(long)]
        delta_k_hex: Option<String>,
        /// Number of avalanche trials.
        #[arg(long, default_value_t = 1024)]
        avalanche_trials: usize,
        /// Number of rounds to study (default = full).  Sets the
        /// avalanche and local-collision round count.
        #[arg(long, default_value_t = 0)]
        rounds: usize,
    },
    /// **AES visual demos** — emit ASCII diagrams for the major
    /// AES attack visualizations: truncated-diff trail, 3-round
    /// integral distinguisher, DFA single-byte-fault propagation,
    /// related-key schedule diffusion.
    AesVisualDemo {
        /// Which demo to run: `truncated-diff`, `integral`, `dfa`,
        /// `key-schedule`, or `all` (default).
        #[arg(long, default_value = "all")]
        demo: String,
    },
    /// **Visual demos for every non-AES attack** — DDT/LAT heat-maps
    /// on S-boxes, Walsh-Hadamard spectra, Pollard ρ trajectories,
    /// HNP recovery curves, Bleichenbacher bias histograms,
    /// length-extension diagrams, Joux multicollision trees, j=0
    /// twist factorisations, birthday-paradox curves.
    VisualAll {
        /// Optional single-demo target: `sbox-ddt`, `sbox-lat`,
        /// `walsh`, `pollard-rho`, `hnp`, `bleichenbacher`,
        /// `length-extension`, `joux`, `j0-twists`, `birthday`,
        /// or `all` (default).
        #[arg(long, default_value = "all")]
        target: String,
    },
    /// **Collaborative (peer-to-peer) Pollard rho** — divide one
    /// ECDLP among many machines with self-verifying distinguished-
    /// point check-ins.  See `docs/POLLARD_COLLAB_DESIGN.md`.
    RhoCollab {
        #[command(subcommand)]
        op: Box<RhoCollabOp>,
    },
    /// Cryptanalysis of ML-KEM and ML-DSA: lattice-attack estimates, working
    /// sieves, and the implementation attacks that actually break deployments.
    Mlwe {
        #[command(subcommand)]
        op: cli_mlwe::MlweOp,
    },
    /// Elliptic-curve challenge corpus: field shapes, j-invariants,
    /// endomorphisms and isogeny volcanoes from a few bits up to 768.
    EcChallenges {
        #[command(subcommand)]
        op: EcChallengesOp,
    },
}

#[derive(Subcommand)]
enum EcChallengesOp {
    /// Print how many instances sit in each family and tier.
    Summary,
    /// List instances. Filters are exact matches on family, tier and tag.
    List {
        #[arg(long)]
        family: Option<String>,
        #[arg(long)]
        tier: Option<String>,
        #[arg(long)]
        tag: Option<String>,
        /// Keep instances whose field has at most this many bits.
        #[arg(long)]
        max_bits: Option<u32>,
    },
    /// Print one instance, including the note and the known-answer relation.
    Show {
        #[arg(long)]
        id: String,
    },
}

#[derive(Subcommand)]
enum RhoCollabOp {
    /// Write a job document that every participant shares.
    Init {
        /// Built-in curve: `demo-small`, `demo-mid`, `demo-32`,
        /// `demo-40`, `secp256k1`.
        #[arg(long, default_value = "demo-32")]
        curve: String,
        /// Plant a secret (hex): the target becomes `secret·P`.
        #[arg(long)]
        secret: Option<String>,
        /// Target point as `x:y` (hex).  Required unless `--secret`.
        #[arg(long)]
        target: Option<String>,
        /// Job label (part of the job id).
        #[arg(long, default_value = "collab")]
        name: String,
        /// Distinguished-point bits; default ≈ ¼·log₂ n.
        #[arg(long)]
        dp_bits: Option<u8>,
        /// Number of r-adding branches.
        #[arg(long, default_value_t = 32)]
        branches: u32,
        /// Use the negation map (x-only DP keys, ≈√2 faster).
        #[arg(long)]
        negation: bool,
        /// Walkers per work unit.
        #[arg(long, default_value_t = 256)]
        unit_size: u64,
        /// Seed mixed into every derivation (re-run with a new one).
        #[arg(long, default_value_t = 0)]
        seed: u64,
        /// Where to write the job document.
        #[arg(long, default_value = "job.json")]
        out: std::path::PathBuf,
        /// Also write it as `<mailbox>/job.json`.
        #[arg(long)]
        mailbox: Option<std::path::PathBuf>,
    },
    /// Walk units, check in, and exchange check-ins with peers.
    Work {
        /// Job document (default: `<mailbox>/job.json`).
        #[arg(long)]
        job: Option<std::path::PathBuf>,
        /// This node's name; lanes are `<node>.<n>`.
        #[arg(long, default_value = "node")]
        node: String,
        /// Worker lanes (threads).
        #[arg(long, default_value_t = 1)]
        threads: usize,
        /// Shared directory transport.
        #[arg(long)]
        mailbox: Option<std::path::PathBuf>,
        /// TCP address to listen on, e.g. `0.0.0.0:7000`.
        #[arg(long)]
        listen: Option<String>,
        /// TCP peers to gossip with (repeatable).
        #[arg(long = "peer")]
        peers: Vec<String>,
        /// Walkers per check-in.
        #[arg(long, default_value_t = 64)]
        checkin_every: u64,
        /// Seconds a silent claim stays live before others take it over.
        #[arg(long, default_value_t = 120)]
        lease_secs: u64,
        /// Seconds between mailbox/peer syncs and status lines.
        #[arg(long, default_value_t = 5)]
        sync_secs: u64,
        /// Stop after this many seconds (0 = until solved).
        #[arg(long, default_value_t = 0)]
        max_seconds: u64,
        /// Stop each lane after this many walkers (0 = until solved).
        #[arg(long, default_value_t = 0)]
        max_walkers: u64,
        /// A cairn node (`http://host:port`, running `cairn serve
        /// --queue`).  Every distinguished point is committed and revealed
        /// as a claim on `--objective`, and the objective's log is merged
        /// back as the shared DP table.
        #[arg(long, requires = "objective")]
        cairn: Option<String>,
        /// The cairn piecework objective id the points are claims on.
        #[arg(long)]
        objective: Option<String>,
        /// Nickname to submit under (default: the node name).  Ignored
        /// when `--identity` is given.
        #[arg(long)]
        submitter: Option<String>,
        /// A cairn identity file (`cairn identity --out FILE`): submit
        /// under its Ed25519 key and sign every record.
        #[arg(long)]
        identity: Option<std::path::PathBuf>,
        /// The cairn objective that pays for `k` itself.  Once the search
        /// solves, `{"k": …}` is committed there and revealed next epoch.
        #[arg(long)]
        answer_objective: Option<String>,
        /// The cairn node's epoch length in seconds (its
        /// `CAIRN_EPOCH_SECONDS`; 600 unless the operator changed it).
        #[arg(long, default_value_t = 600)]
        cairn_epoch_secs: u64,
        /// Where pending commitments are kept between runs (default:
        /// `<node>.cairn.json` next to the job).
        #[arg(long)]
        cairn_state: Option<std::path::PathBuf>,
    },
    /// Show merged progress from a mailbox, peers, and/or a cairn log.
    Status {
        #[arg(long)]
        job: Option<std::path::PathBuf>,
        #[arg(long)]
        mailbox: Option<std::path::PathBuf>,
        #[arg(long = "peer")]
        peers: Vec<String>,
        /// Read the objective's accepted points from this cairn node.
        #[arg(long, requires = "objective")]
        cairn: Option<String>,
        #[arg(long)]
        objective: Option<String>,
        /// Emit JSON instead of text.
        #[arg(long)]
        json: bool,
        #[arg(long, default_value_t = 120)]
        lease_secs: u64,
    },
}

fn cmd_ec_challenges(op: EcChallengesOp) {
    use cryptanalysis_suite::cryptanalysis::ec_challenges::{self, corpus};
    let corpus = corpus();
    match op {
        EcChallengesOp::Summary => print!("{}", ec_challenges::format_summary(corpus)),
        EcChallengesOp::List {
            family,
            tier,
            tag,
            max_bits,
        } => {
            let rows = ec_challenges::select(
                corpus,
                family.as_deref(),
                tier.as_deref(),
                tag.as_deref(),
                max_bits,
            );
            print!("{}", ec_challenges::format_list(&rows));
        }
        EcChallengesOp::Show { id } => match ec_challenges::find(corpus, &id) {
            Some(inst) => print!("{}", ec_challenges::format_instance(inst)),
            None => {
                eprintln!("no challenge named {id}");
                std::process::exit(1);
            }
        },
    }
}

fn main() {
    let cli = Cli::parse();
    // Honour the --color flag before any visual code runs.
    match cli.color.as_str() {
        "always" | "1" | "yes" | "on" => cryptanalysis_suite::visualize::color::set_enabled(true),
        "never" | "0" | "no" | "off" => cryptanalysis_suite::visualize::color::set_enabled(false),
        _ => {} // "auto": leave to env-var + TTY detection
    }
    run(cli.command);
}

fn run(op: Cmd) {
    use cryptanalysis_suite::cryptanalysis::auto_attack::{auto_attack_with, AutoAttackOptions};
    use cryptanalysis_suite::cryptanalysis::boomerang::{
        boomerang_distinguisher, rectangle_attack,
    };
    use cryptanalysis_suite::cryptanalysis::cipher_registry::{list_ciphers, RegisteredCipher};
    use cryptanalysis_suite::cryptanalysis::research_bench::run_full_bench;
    match op {
        Cmd::ListCiphers => {
            println!("Registered ciphers:");
            for name in list_ciphers() {
                if let Some(c) = RegisteredCipher::from_name(name) {
                    let e = c.entry();
                    println!(
                        "  {:<22} {} block={}B rounds={}",
                        name, e.description, e.block_bytes, e.rounds,
                    );
                }
            }
        }
        Cmd::Auto {
            cipher,
            boomerang_pairs,
            rectangle_pool,
            trail_threshold_neg_log2,
            trail_top_k,
        } => {
            let opts = AutoAttackOptions {
                boomerang_pairs,
                rectangle_pool,
                trail_threshold: 2f64.powi(-(trail_threshold_neg_log2 as i32)),
                trail_top_k,
            };
            match auto_attack_with(&cipher, opts) {
                Ok(r) => {
                    println!("{}", r.markdown);
                    eprintln!(
                        "[auto-attack] {} sections in {} ms",
                        r.sections_run, r.elapsed_ms,
                    );
                }
                Err(e) => {
                    eprintln!("error: {}", e);
                    eprintln!("Try one of: {}", list_ciphers().join(", "));
                    std::process::exit(1);
                }
            }
        }
        Cmd::Boomerang {
            cipher,
            alpha,
            delta,
            pairs,
        } => {
            let c = match RegisteredCipher::from_name(&cipher) {
                Some(c) => c,
                None => {
                    eprintln!("error: unknown cipher: {}", cipher);
                    std::process::exit(1);
                }
            };
            let entry = c.entry();
            let alpha_bytes = match alpha {
                Some(h) => from_hex(&h).expect("bad alpha hex"),
                None => entry.canonical_alpha.clone(),
            };
            let delta_bytes = match delta {
                Some(h) => from_hex(&h).expect("bad delta hex"),
                None => entry.canonical_delta.clone(),
            };
            if alpha_bytes.len() != entry.block_bytes || delta_bytes.len() != entry.block_bytes {
                eprintln!(
                    "error: alpha/delta must be {} bytes for this cipher",
                    entry.block_bytes
                );
                std::process::exit(1);
            }
            let t0 = std::time::Instant::now();
            let r = boomerang_distinguisher(&c, &alpha_bytes, &delta_bytes, pairs, None);
            let elapsed = t0.elapsed().as_millis();
            println!("# Boomerang distinguisher on `{}`", cipher);
            println!();
            println!("- elapsed:       {} ms", elapsed);
            println!("- right quartets: {} / {}", r.right_quartets, r.n_pairs);
            println!("- empirical p:   {:.4e}", r.empirical_probability);
            println!("- random baseline: {:.4e}", r.random_baseline);
            println!(
                "- distinguishes from random (10×): {}",
                if r.distinguishes_from_random(10.0) {
                    "yes"
                } else {
                    "no"
                },
            );
        }
        Cmd::Rectangle {
            cipher,
            alpha,
            delta,
            pool,
        } => {
            let c = match RegisteredCipher::from_name(&cipher) {
                Some(c) => c,
                None => {
                    eprintln!("error: unknown cipher: {}", cipher);
                    std::process::exit(1);
                }
            };
            let entry = c.entry();
            let alpha_bytes = match alpha {
                Some(h) => from_hex(&h).expect("bad alpha hex"),
                None => entry.canonical_alpha.clone(),
            };
            let delta_bytes = match delta {
                Some(h) => from_hex(&h).expect("bad delta hex"),
                None => entry.canonical_delta.clone(),
            };
            let t0 = std::time::Instant::now();
            let r = rectangle_attack(&c, &alpha_bytes, &delta_bytes, pool, None);
            let elapsed = t0.elapsed().as_millis();
            println!("# Rectangle attack on `{}`", cipher);
            println!();
            println!("- elapsed:           {} ms", elapsed);
            println!("- pool size:         {}", r.pool_size);
            println!("- right rectangles:  {}", r.right_quartets);
        }
        Cmd::Sbox { cipher } => {
            let c = match RegisteredCipher::from_name(&cipher) {
                Some(c) => c,
                None => {
                    eprintln!("error: unknown cipher: {}", cipher);
                    std::process::exit(1);
                }
            };
            match c.sbox() {
                Some(sbox) => {
                    let r = sbox.report();
                    println!("# S-box report for `{}`", cipher);
                    println!();
                    println!("- bits in / out:                 {} / {}", r.n_in, r.n_out);
                    println!("- bijective:                     {}", r.bijective);
                    println!("- balanced:                      {}", r.balanced);
                    println!(
                        "- differential uniformity:       {}",
                        r.differential_uniformity
                    );
                    println!(
                        "- max differential probability:  {:.4}",
                        r.max_differential_probability
                    );
                    println!("- max linear bias:               {:.4}", r.max_linear_bias);
                    println!("- nonlinearity:                  {}", r.nonlinearity);
                    println!("- algebraic degree:              {}", r.algebraic_degree);
                    println!(
                        "- boomerang uniformity:          {}",
                        r.boomerang_uniformity
                            .map(|v| v.to_string())
                            .unwrap_or_else(|| "—".into()),
                    );
                    println!("- max DLCT bias:                 {:.4}", r.max_dlct_bias);
                }
                None => {
                    eprintln!("error: cipher {} has no exposed S-box", cipher);
                    std::process::exit(1);
                }
            }
        }
        Cmd::Bench => {
            eprintln!("Running full research bench (this takes ~15-30 s in release mode)...");
            let report = run_full_bench(1);
            println!("{}", report);
        }
        Cmd::RhoCollab { op } => cmd_rho_collab(*op),
        Cmd::Mlwe { op } => cli_mlwe::run(op),
        Cmd::EcChallenges { op } => cmd_ec_challenges(op),
        Cmd::HashAuto { hash } => {
            use cryptanalysis_suite::cryptanalysis::hash_attacks::auto_hash_attack;
            match auto_hash_attack(&hash) {
                Ok(md) => println!("{}", md),
                Err(e) => {
                    eprintln!("error: {}", e);
                    std::process::exit(1);
                }
            }
        }
        Cmd::LengthExtension {
            hash,
            secret_len,
            message_hex,
            suffix_hex,
            digest_hex,
        } => {
            use cryptanalysis_suite::cryptanalysis::hash_attacks::{
                length_extension_attack, Md4, Md5, MerkleDamgardHash, Sha1,
            };
            let message = from_hex(&message_hex).expect("bad message hex");
            let suffix = from_hex(&suffix_hex).expect("bad suffix hex");
            let digest = from_hex(&digest_hex).expect("bad digest hex");
            let prefix_len = secret_len + message.len();
            fn report_lex<H: MerkleDamgardHash>(
                hash: &H,
                digest: &[u8],
                prefix_len: usize,
                message: &[u8],
                suffix: &[u8],
            ) {
                let (forged, glue) = length_extension_attack(hash, digest, prefix_len, suffix);
                println!("# Length-extension attack on `{}`", hash.name());
                println!();
                println!("Forged digest: {}", to_hex(&forged));
                println!("Glue padding bytes ({} B): {}", glue.len(), to_hex(&glue));
                println!();
                println!("Effective extended message (without secret):");
                println!(
                    "  message ({}B) || glue ({}B) || suffix ({}B)",
                    message.len(),
                    glue.len(),
                    suffix.len()
                );
                let mut combined = Vec::new();
                combined.extend_from_slice(message);
                combined.extend_from_slice(&glue);
                combined.extend_from_slice(suffix);
                println!("Hex: {}", to_hex(&combined));
            }
            match hash.as_str() {
                "md4" => report_lex(&Md4, &digest, prefix_len, &message, &suffix),
                "md5" => report_lex(&Md5, &digest, prefix_len, &message, &suffix),
                "sha1" => report_lex(&Sha1, &digest, prefix_len, &message, &suffix),
                other => {
                    eprintln!("error: unknown hash '{}' (try md4, md5, sha1)", other);
                    std::process::exit(1);
                }
            }
        }
        Cmd::AesRelatedKey {
            key_bits,
            delta_k_hex,
            avalanche_trials,
            rounds,
        } => {
            use cryptanalysis_suite::cryptanalysis::aes::related_key::{
                biryukov_khovratovich_4round_demo, format_key_schedule_diff,
                key_schedule_difference, related_key_avalanche,
            };
            use cryptanalysis_suite::symmetric::aes::AesKey;
            let key_bytes = match key_bits {
                128 => 16,
                256 => 32,
                _ => {
                    eprintln!("error: --key-bits must be 128 or 256");
                    std::process::exit(1);
                }
            };
            let default_rounds = if key_bits == 128 { 10 } else { 14 };
            let rounds = if rounds == 0 { default_rounds } else { rounds };
            let delta_k: Vec<u8> = match &delta_k_hex {
                Some(h) => {
                    let v = from_hex(h).expect("bad --delta-k-hex");
                    if v.len() != key_bytes {
                        eprintln!(
                            "error: --delta-k-hex must be {} bytes (got {})",
                            key_bytes,
                            v.len()
                        );
                        std::process::exit(1);
                    }
                    v
                }
                None => {
                    let mut d = vec![0u8; key_bytes];
                    d[0] = 0x01;
                    d
                }
            };
            // 1. Key-schedule difference propagation.
            let zero_key_bytes = vec![0u8; key_bytes];
            let zero_key = AesKey::new(&zero_key_bytes).unwrap();
            let diff = key_schedule_difference(&zero_key, &delta_k);
            println!(
                "# AES-{} related-key attack against ΔK = 0x{}",
                key_bits,
                to_hex(&delta_k)
            );
            println!();
            println!("## Key-schedule difference propagation\n");
            println!("{}", format_key_schedule_diff(&diff));
            // 2. Related-key avalanche (AES-128 only — the avalanche
            // function uses ReducedAes128 which is 16-byte-key only).
            if key_bits == 128 {
                println!(
                    "## Related-key avalanche ({} rounds, {} trials)\n",
                    rounds, avalanche_trials
                );
                let zero_key_16 = [0u8; 16];
                let mut dk16 = [0u8; 16];
                dk16.copy_from_slice(&delta_k);
                let r = related_key_avalanche(&zero_key_16, &dk16, rounds, avalanche_trials);
                println!("- mean Hamming distance: {:.2} bits", r.mean_distance_bits);
                println!("- ideal-cipher baseline: {:.2} bits", r.ideal_baseline);
                println!("- bias from ideal:       {:.2} bits", r.bias);
                println!();
                println!("## Biryukov-Khovratovich-style local collision\n");
                println!("{} trials at {} rounds:", avalanche_trials, rounds);
                let r = biryukov_khovratovich_4round_demo(avalanche_trials, rounds);
                println!(
                    "- low-Hamming-distance hits: {} / {}",
                    r.collisions, r.n_trials
                );
                println!(
                    "- empirical hit rate:        {:.4}",
                    r.empirical_probability
                );
                println!("- random baseline (Hd≤16 in 128 bits): ≈ 2⁻⁷⁹");
            } else {
                println!("(Related-key avalanche + local-collision demo only available for AES-128; key-schedule diffusion table above already shows the AES-256 weakness.)");
            }
        }
        Cmd::AesVisualDemo { demo } => {
            use cryptanalysis_suite::cryptanalysis::aes::{
                dfa::{dfa_per_column_candidates, format_dfa_visualization, inject_fault_round_9},
                higher_order::{integral_distinguisher_3_round, render_integral_visualization},
                reduced::ReducedAes128,
                related_key::{format_key_schedule_diff, key_schedule_difference},
                truncated_diff::{
                    propagate_truncated_round, render_trail_diagram, TruncatedPattern,
                },
            };
            use cryptanalysis_suite::symmetric::aes::AesKey;
            let run_truncated = |x: &str| -> bool { x == "all" || x == "truncated-diff" };
            let run_integral = |x: &str| -> bool { x == "all" || x == "integral" };
            let run_dfa = |x: &str| -> bool { x == "all" || x == "dfa" };
            let run_ks = |x: &str| -> bool { x == "all" || x == "key-schedule" };
            if run_truncated(&demo) {
                println!("\n## (1) Truncated-differential trail on AES (single active byte)\n");
                let mut current = TruncatedPattern(1);
                let mut steps = Vec::new();
                for _ in 0..4 {
                    let step = propagate_truncated_round(current);
                    let mut next = 0u16;
                    for c in 0..4 {
                        let n = *step.mc_output_counts[c].iter().min().unwrap();
                        for r in 0..n as usize {
                            next |= 1u16 << (4 * c + r);
                        }
                    }
                    current = TruncatedPattern(next);
                    steps.push(step);
                }
                println!("{}", render_trail_diagram(&steps));
            }
            if run_integral(&demo) {
                println!("\n## (2) Square / integral distinguisher on 3-round AES\n");
                let key = [0u8; 16];
                let other = [0u8; 15];
                let xor_sum = integral_distinguisher_3_round(&key, &other);
                println!("{}", render_integral_visualization(&xor_sum));
            }
            if run_dfa(&demo) {
                println!("\n## (3) DFA / Piret-Quisquater single-byte fault on AES-128\n");
                let key_bytes = [
                    0x2b, 0x7e, 0x15, 0x16, 0x28, 0xae, 0xd2, 0xa6, 0xab, 0xf7, 0x15, 0x88, 0x09,
                    0xcf, 0x4f, 0x3c,
                ];
                let cipher = ReducedAes128::new(&key_bytes, 10, false);
                let pt = [0x6bu8; 16];
                let (correct, faulted) = inject_fault_round_9(&cipher, &pt, 0, 0xCC);
                let cands = dfa_per_column_candidates(&correct, &faulted);
                println!("{}", format_dfa_visualization(&correct, &faulted, &cands));
            }
            if run_ks(&demo) {
                println!("\n## (4) Related-key schedule diffusion (AES-256 vs AES-128)\n");
                for &(bits, label) in &[(128u32, "AES-128"), (256u32, "AES-256")] {
                    let key_bytes = vec![0u8; (bits / 8) as usize];
                    let key = AesKey::new(&key_bytes).unwrap();
                    let mut delta = vec![0u8; (bits / 8) as usize];
                    delta[0] = 0x01;
                    let diff = key_schedule_difference(&key, &delta);
                    println!("\n### {} (ΔK = single byte at position 0)\n", label);
                    println!("{}", format_key_schedule_diff(&diff));
                }
            }
        }
        Cmd::VisualAll { target } => {
            use cryptanalysis_suite::cryptanalysis::visual_demos::{
                demo_birthday_paradox, demo_bleichenbacher_bias, demo_hnp_recovery_curve,
                demo_j0_twist_factors, demo_joux_multicollision, demo_length_extension_diagram,
                demo_pollard_rho_path, demo_sbox_ddt_heatmap, demo_sbox_lat_heatmap,
                demo_walsh_spectrum, run_all_visual_demos,
            };
            let out: String = match target.as_str() {
                "sbox-ddt" => demo_sbox_ddt_heatmap(),
                "sbox-lat" => demo_sbox_lat_heatmap(),
                "walsh" => demo_walsh_spectrum(),
                "pollard-rho" => demo_pollard_rho_path(),
                "hnp" => demo_hnp_recovery_curve(),
                "bleichenbacher" => demo_bleichenbacher_bias(),
                "length-extension" => demo_length_extension_diagram(),
                "joux" => demo_joux_multicollision(),
                "j0-twists" => demo_j0_twist_factors(),
                "birthday" => demo_birthday_paradox(),
                "all" => run_all_visual_demos(),
                other => {
                    eprintln!("error: unknown target '{}'; try `all` or one of: sbox-ddt, sbox-lat, walsh, pollard-rho, hnp, bleichenbacher, length-extension, joux, j0-twists, birthday", other);
                    std::process::exit(1);
                }
            };
            println!("{}", out);
        }
    }
}

fn cmd_rho_collab(op: RhoCollabOp) {
    use cryptanalysis_suite::cryptanalysis::pollard_collab::cairn::{
        wall_clock, CairnConfig, CairnTransport, Submitter,
    };
    use cryptanalysis_suite::cryptanalysis::pollard_collab::{
        demo_curve, run_lane, sync_with_peer, JobSpec, LaneOptions, Mailbox, PeerServer,
        SharedState, DEMO_CURVES,
    };
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::sync::{Arc, Mutex};
    use std::time::{Duration, Instant};

    fn die(msg: impl std::fmt::Display) -> ! {
        eprintln!("error: {msg}");
        std::process::exit(1);
    }
    fn parse_hex(s: &str) -> BigUint {
        BigUint::parse_bytes(s.trim().trim_start_matches("0x").as_bytes(), 16)
            .unwrap_or_else(|| die(format!("bad hex `{s}`")))
    }
    fn load_spec(
        job: &Option<std::path::PathBuf>,
        mailbox: &Option<std::path::PathBuf>,
    ) -> JobSpec {
        match (job, mailbox) {
            (Some(p), _) => {
                let s = std::fs::read_to_string(p)
                    .unwrap_or_else(|e| die(format!("{}: {e}", p.display())));
                JobSpec::from_json(&s).unwrap_or_else(|e| die(e))
            }
            (None, Some(d)) => Mailbox::read_job(d).unwrap_or_else(|e| die(e)),
            (None, None) => die("pass --job <file> or --mailbox <dir>"),
        }
    }

    /// Open the cairn transport the flags describe, if `--cairn` was given.
    #[allow(clippy::too_many_arguments)]
    fn open_cairn(
        url: &Option<String>,
        objective: &Option<String>,
        submitter: &Option<String>,
        identity: &Option<std::path::PathBuf>,
        answer_objective: &Option<String>,
        epoch_secs: u64,
        state_path: Option<std::path::PathBuf>,
        default_name: &str,
    ) -> Option<CairnTransport> {
        let url = url.as_ref()?;
        let objective_id = objective
            .clone()
            .unwrap_or_else(|| die("--cairn needs --objective <id>"));
        let who = match identity {
            Some(path) => Submitter::from_identity_file(path).unwrap_or_else(|e| die(e)),
            None => Submitter::Nickname(
                submitter
                    .clone()
                    .unwrap_or_else(|| default_name.to_string()),
            ),
        };
        let transport = CairnTransport::open(CairnConfig {
            url: url.trim_end_matches('/').to_string(),
            objective_id: objective_id.clone(),
            submitter: who,
            answer_objective: answer_objective.clone(),
            epoch_secs,
            state_path,
            clock: wall_clock(),
        })
        .unwrap_or_else(|e| die(e));
        let short = if objective_id.len() > 23 {
            format!("{}…", &objective_id[..23])
        } else {
            objective_id
        };
        eprintln!(
            "[cairn] {url} · objective {short} · submitting as {}{}",
            transport.submitter(),
            if transport.pending() > 0 {
                format!(
                    " · {} commitment(s) pending from a previous run",
                    transport.pending()
                )
            } else {
                String::new()
            }
        );
        Some(transport)
    }

    match op {
        RhoCollabOp::Init {
            curve,
            secret,
            target,
            name,
            dp_bits,
            branches,
            negation,
            unit_size,
            seed,
            out,
            mailbox,
        } => {
            let params = demo_curve(&curve).unwrap_or_else(|| {
                die(format!(
                    "unknown curve `{curve}`; try {}",
                    DEMO_CURVES.join(", ")
                ))
            });
            let q = match (&secret, &target) {
                (Some(s), _) => {
                    let x = parse_hex(s) % &params.n;
                    params.generator().scalar_mul(&x, &params.a_fe())
                }
                (None, Some(t)) => {
                    let (xs, ys) = t
                        .split_once(':')
                        .unwrap_or_else(|| die("--target must be `x:y` hex"));
                    Point::Affine {
                        x: params.fe(parse_hex(xs)),
                        y: params.fe(parse_hex(ys)),
                    }
                }
                (None, None) => die("pass --secret <hex> (planted demo) or --target x:y"),
            };
            let mut spec = JobSpec::new(&params, &q, &name, seed).unwrap_or_else(|e| die(e));
            if let Some(b) = dp_bits {
                spec.dp_bits = b;
            }
            spec.num_branches = branches;
            spec.negation_map = negation;
            spec.unit_size = unit_size;
            let ctx = spec.build().unwrap_or_else(|e| die(e));
            std::fs::write(&out, spec.to_json())
                .unwrap_or_else(|e| die(format!("{}: {e}", out.display())));
            if let Some(d) = &mailbox {
                let mb = Mailbox::open(d).unwrap_or_else(|e| die(e));
                mb.write_job(&spec).unwrap_or_else(|e| die(e));
            }
            println!("job id:          {}", ctx.job_id);
            println!(
                "curve:           {} ({} bits)",
                params.name,
                params.n.bits()
            );
            println!(
                "dp_bits:         {}  (mean trail 2^{})",
                spec.dp_bits, spec.dp_bits
            );
            println!("unit size:       {} walkers", spec.unit_size);
            println!("expected steps:  {:.3e}", ctx.expected_steps());
            println!("expected DPs:    {:.3e}", ctx.expected_dps());
            println!("written:         {}", out.display());
            if let Some(d) = mailbox {
                println!("mailbox:         {}", d.join("job.json").display());
            }
        }

        RhoCollabOp::Work {
            job,
            node,
            threads,
            mailbox,
            listen,
            peers,
            checkin_every,
            lease_secs,
            sync_secs,
            max_seconds,
            max_walkers,
            cairn,
            objective,
            submitter,
            identity,
            answer_objective,
            cairn_epoch_secs,
            cairn_state,
        } => {
            let spec = load_spec(&job, &mailbox);
            let ctx = Arc::new(spec.build().unwrap_or_else(|e| die(e)));
            let state = Arc::new(Mutex::new(SharedState::new(&ctx)));
            let cairn_state = cairn_state.or_else(|| {
                cairn.as_ref().map(|_| {
                    let dir = job
                        .as_ref()
                        .and_then(|p| p.parent().map(|d| d.to_path_buf()))
                        .or_else(|| mailbox.clone())
                        .unwrap_or_else(|| std::path::PathBuf::from("."));
                    dir.join(format!("{node}.cairn.json"))
                })
            });
            let cairn = open_cairn(
                &cairn,
                &objective,
                &submitter,
                &identity,
                &answer_objective,
                cairn_epoch_secs,
                cairn_state,
                &node,
            )
            .map(|t| Arc::new(Mutex::new(t)));
            if let Some(c) = &cairn {
                let mut st = state.lock().unwrap();
                match c.lock().unwrap().sync(&ctx, &mut st) {
                    Ok(r) => eprintln!(
                        "[cairn] log read: {} points merged, {} rejected, {} revealed",
                        r.accepted_dps, r.rejected_dps, r.revealed
                    ),
                    Err(e) => eprintln!("[cairn] first sync failed: {e}"),
                }
            }
            let mbox = mailbox.as_ref().map(|d| {
                let mut mb = Mailbox::open(d).unwrap_or_else(|e| die(e));
                let (n, _) = mb
                    .sync(&ctx, &mut state.lock().unwrap())
                    .unwrap_or_else(|e| die(e));
                eprintln!("[collab] mailbox {}: merged {n} check-ins", d.display());
                Arc::new(Mutex::new(mb))
            });
            let _server = listen.as_ref().map(|addr| {
                let s = PeerServer::start(addr, Arc::clone(&ctx), Arc::clone(&state))
                    .unwrap_or_else(|e| die(format!("listen {addr}: {e}")));
                eprintln!("[collab] listening on {}", s.local_addr());
                s
            });
            let do_sync = |verbose: bool| {
                for p in &peers {
                    match sync_with_peer(p.as_str(), &ctx, &state) {
                        Ok(r) => {
                            if verbose && (r.received > 0 || r.sent > 0) {
                                eprintln!(
                                    "[collab] {p}: received {} sent {} rejected {}/{}",
                                    r.received, r.sent, r.rejected_here, r.rejected_there
                                );
                            }
                        }
                        Err(e) => {
                            if verbose {
                                eprintln!("[collab] {p}: sync failed: {e}");
                            }
                        }
                    }
                }
                if let Some(mb) = &mbox {
                    let mut mb = mb.lock().unwrap();
                    let mut st = state.lock().unwrap();
                    if let Ok((n, rej)) = mb.sync(&ctx, &mut st) {
                        if verbose && (n > 0 || rej > 0) {
                            eprintln!("[collab] mailbox: +{n} check-ins, {rej} DPs rejected");
                        }
                    }
                    // Bridge: anything learned over TCP goes into the
                    // directory too.
                    if let Err(e) = mb.publish_missing(&st) {
                        eprintln!("[collab] mailbox relay failed: {e}");
                    }
                }
                if let Some(c) = &cairn {
                    let mut st = state.lock().unwrap();
                    let mut c = c.lock().unwrap();
                    match c.sync(&ctx, &mut st) {
                        Ok(r) => {
                            if verbose && (r.accepted_dps > 0 || r.revealed > 0 || r.refused > 0) {
                                eprintln!(
                                    "[cairn] +{} points from the log ({} rejected), {} revealed, {} refused",
                                    r.accepted_dps, r.rejected_dps, r.revealed, r.refused
                                );
                            }
                        }
                        Err(e) => {
                            if verbose {
                                eprintln!("[cairn] sync failed: {e}");
                            }
                        }
                    }
                }
            };
            do_sync(true);

            eprintln!(
                "[collab] job {} · node {node} · {threads} lane(s) · expected {:.3e} steps",
                &ctx.job_id[..16],
                ctx.expected_steps()
            );
            let stop = Arc::new(AtomicBool::new(false));
            let start = Instant::now();
            let handles: Vec<_> = (0..threads.max(1))
                .map(|lane| {
                    let ctx = Arc::clone(&ctx);
                    let state = Arc::clone(&state);
                    let stop = Arc::clone(&stop);
                    let mbox = mbox.clone();
                    let cairn = cairn.clone();
                    let opts = LaneOptions {
                        checkin_every,
                        lease_secs,
                        max_walkers,
                        ..LaneOptions::new(&format!("{node}.{lane}"))
                    };
                    std::thread::spawn(move || {
                        run_lane(
                            &ctx,
                            &state,
                            &opts,
                            &mut |ci| {
                                if let Some(mb) = &mbox {
                                    if let Err(e) = mb.lock().unwrap().publish(ci) {
                                        eprintln!("[collab] publish failed: {e}");
                                    }
                                }
                                if let Some(c) = &cairn {
                                    match c.lock().unwrap().publish(&ctx, ci) {
                                        Ok(r) if r.committed > 0 => eprintln!(
                                            "[cairn] committed {} point(s); reveal follows next epoch",
                                            r.committed
                                        ),
                                        Ok(_) => {}
                                        Err(e) => eprintln!("[cairn] commit failed: {e}"),
                                    }
                                }
                            },
                            &|| stop.load(Ordering::Relaxed),
                        )
                    })
                })
                .collect();

            let tick = Duration::from_secs(sync_secs.max(1));
            let mut last_sync = Instant::now();
            loop {
                std::thread::sleep(Duration::from_millis(250));
                let lanes_done = handles.iter().all(|h| h.is_finished());
                let solved = state.lock().unwrap().solution.is_some();
                let timed_out = max_seconds > 0 && start.elapsed().as_secs() >= max_seconds;
                let due = last_sync.elapsed() >= tick;
                if due || solved || lanes_done || timed_out {
                    last_sync = Instant::now();
                    do_sync(true);
                    let st = state.lock().unwrap();
                    let p = st.progress(
                        &ctx,
                        cryptanalysis_suite::cryptanalysis::pollard_collab::state::now_secs(),
                        lease_secs,
                    );
                    eprintln!(
                        "[collab] {:>6.1}s  steps {:>10}  ({:>5.1}% of expected)  DPs {:>7}  units done {} active {}  peers {}  rejected {}",
                        start.elapsed().as_secs_f64(),
                        p.steps,
                        100.0 * p.fraction,
                        p.dps_stored,
                        p.units_completed,
                        p.units_active,
                        p.peers,
                        p.rejected_dps,
                    );
                    if let Some(c) = &cairn {
                        let c = c.lock().unwrap();
                        let s = c.stats();
                        eprintln!(
                            "[cairn]  committed {}  revealed {}  pending {}  refused {}  paid {} unit(s) = {}  rejected {}  log points {}",
                            s.committed, s.revealed, c.pending(), s.refused, s.paid_units, s.paid_total, s.rejected, s.log_dps,
                        );
                    }
                }
                if solved || lanes_done || timed_out {
                    break;
                }
            }
            stop.store(true, Ordering::Relaxed);
            for h in handles {
                let _ = h.join();
            }
            // Final exchange so peers learn the outcome.
            do_sync(false);
            let st = state.lock().unwrap();
            if let Some(c) = &cairn {
                let c = c.lock().unwrap();
                if c.pending() > 0 {
                    eprintln!(
                        "[cairn] {} commitment(s) still wait for the epoch to turn; run `work` again \
                         (same node name and state file) to reveal them",
                        c.pending()
                    );
                }
            }
            match &st.solution {
                Some(x) => {
                    println!("solution: {}", x.to_str_radix(16));
                    println!("verified: {}", ctx.g.scalar_mul(x, &ctx.a) == ctx.q);
                }
                None => {
                    println!(
                        "solution: not found (stopped after {:.1}s)",
                        start.elapsed().as_secs_f64()
                    );
                    std::process::exit(2);
                }
            }
        }

        RhoCollabOp::Status {
            job,
            mailbox,
            peers,
            cairn,
            objective,
            json,
            lease_secs,
        } => {
            let spec = load_spec(&job, &mailbox);
            let ctx = spec.build().unwrap_or_else(|e| die(e));
            let state = Mutex::new(SharedState::new(&ctx));
            if let Some(d) = &mailbox {
                let mut mb = Mailbox::open(d).unwrap_or_else(|e| die(e));
                mb.sync(&ctx, &mut state.lock().unwrap())
                    .unwrap_or_else(|e| die(e));
            }
            if let Some(mut c) =
                open_cairn(&cairn, &objective, &None, &None, &None, 600, None, "status")
            {
                match c.sync(&ctx, &mut state.lock().unwrap()) {
                    Ok(r) => eprintln!(
                        "[cairn] {} accepted point(s) in the log, {} rejected here",
                        r.accepted_dps, r.rejected_dps
                    ),
                    Err(e) => eprintln!("[cairn] {e}"),
                }
            }
            for p in &peers {
                if let Err(e) = sync_with_peer(p.as_str(), &ctx, &state) {
                    eprintln!("[collab] {p}: {e}");
                }
            }
            let st = state.lock().unwrap();
            let now = cryptanalysis_suite::cryptanalysis::pollard_collab::state::now_secs();
            let p = st.progress(&ctx, now, lease_secs);
            if json {
                println!("{}", serde_json::to_string_pretty(&p).unwrap());
                return;
            }
            println!("job id:        {}", ctx.job_id);
            println!("peers seen:    {}   check-ins: {}", p.peers, p.checkins);
            println!(
                "steps:         {}   ({:.1}% of expected {:.3e})",
                p.steps,
                100.0 * p.fraction,
                p.expected_steps
            );
            println!(
                "DPs stored:    {}   (expected ≈ {:.3e}; {} rejected)",
                p.dps_stored, p.expected_dps, p.rejected_dps
            );
            println!(
                "units:         {} completed, {} active",
                p.units_completed, p.units_active
            );
            match &p.solution {
                Some(x) => println!("solution:      {x}"),
                None => println!("solution:      not yet"),
            }
            let units = st.units(now, lease_secs);
            if !units.is_empty() {
                println!();
                println!(
                    "{:>8} {:>10} {:>10} {:>6} {:>5}  owner",
                    "unit", "walkers", "steps", "dps", "dead"
                );
                for u in units.iter().take(40) {
                    println!(
                        "{:>8} {:>10} {:>10} {:>6} {:>5}  {}",
                        u.unit,
                        format!("{}/{}", u.walkers_done, ctx.spec.unit_size),
                        u.steps,
                        u.dps,
                        u.dead_trails,
                        if u.completed {
                            "done".to_string()
                        } else {
                            u.owner.clone().unwrap_or_else(|| "(lease expired)".into())
                        }
                    );
                }
                if units.len() > 40 {
                    println!("… {} more units", units.len() - 40);
                }
            }
        }
    }
}
