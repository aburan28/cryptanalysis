//! Values for the independent Python check (`check_points.py`): group law,
//! scalar multiplication, Frobenius, canonical forms and one step of each walk
//! design, at n = 131 (inputs points) and n = 83 (generator multiples).
//!
//!   emit <inputs131.json> > emit.json
use n131_ref_walk::*;

fn p(pt: &Pt) -> String {
    if pt.inf {
        "null".into()
    } else {
        format!("[\"{}\",\"{}\"]", hex(&pt.x), hex(&pt.y))
    }
}

fn block<F: Field>(c: &Curve<F>, pts: &[Pt], rng: &mut Rng, bits: u32) -> String {
    let mut rows = vec![];
    for i in 0..pts.len() - 1 {
        let (a, b) = (pts[i], pts[i + 1]);
        let mut k = [rng.next(), rng.next(), rng.next()];
        for l in 0..3 {
            let keep = bits.saturating_sub(64 * l as u32).min(64);
            k[l] = if keep == 64 { k[l] } else if keep == 0 { 0 } else { k[l] & ((1u64 << keep) - 1) };
        }
        let t = (rng.next() % F::N as u64) as u32;
        let (cp, _, ck, cn) = c.canon_with::<false>(&a);
        // one Bailey step from a (single lane, no batching: the same formula)
        let xc = c.to_nb(&a.x);
        let j = 3 + ((popcnt(&xc) >> 1) & 7);
        let s = c.frob(&a, j);
        let bailey = c.add(&a, &s);
        rows.push(format!(
            "{{\"P\":{},\"Q\":{},\"sum\":{},\"dbl\":{},\"neg\":{},\"k\":\"{}\",\"kP\":{},\"t\":{t},\"frobP\":{},\"canon\":{},\"canon_k\":{ck},\"canon_neg\":{cn},\"hw\":{},\"bailey_j\":{j},\"bailey_next\":{}}}",
            p(&a), p(&b), p(&c.add(&a, &b)), p(&c.double(&a)), p(&c.neg(&a)), hex(&k), p(&c.smul(&a, &k)), p(&c.frob(&a, t)),
            p(&cp), popcnt(&xc), p(&bailey)
        ));
    }
    rows.join(",\n")
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let text = std::fs::read_to_string(&a[1]).unwrap();
    let c131 = Curve::<F131>::new(0);
    let pts131: Vec<Pt> = hex_points(&text, "starts").into_iter().take(9).collect();
    let mut rng = Rng(20261015);
    let b131 = block(&c131, &pts131, &mut rng, 130);
    let c83 = Curve::<F83>::new(1);
    let g = n83::gen();
    let mut pts83 = vec![];
    for i in 0..9u64 {
        pts83.push(c83.smul(&g, &[1 + rng.next() % (n83::R - 1) + i, 0, 0]));
    }
    let b83 = block(&c83, &pts83, &mut rng, 83);
    println!("{{\"n131\":[\n{b131}\n],\n\"n83\":[\n{b83}\n]}}");
}
