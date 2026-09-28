# Change detection on real 2026 amendments of other RBI Directions

Old = latest Wayback capture before the amendments; new = current rbi.org.in page.
Ground truth = clauses RBI marked as amended after the old capture, extended across the
'[ ... ]' range RBI opens at each marker (an inserted block has one footnote).
Counts only; no language model involved. KYC (2 amendments) is in change_detection.md.

| Direction | Old capture | Amendments (effective) | Found | Missed | Extra | Extra not under a marked clause |
|---|---|---|---|---|---|---|
| Responsible Business Conduct | 2026-06-15 | 2026-07-01 | 4/5 | 1 | 0 | 0 |
| Financial Statements: Presentation and Disclosures | - | - | - | - | - | no dated amendment markers |
| Resolution of Stressed Assets | 2026-06-14 | 2026-07-01 | 31/31 | 0 | 2 | 2 |
| Income Recognition, Asset Classification and Provisioning | 2026-06-17 | 2026-07-01 | 11/11 | 0 | 6 | 6 |
| Classification, Valuation and Operation of Investment Portfolio | - | - | - | - | - | no dated amendment markers |
| Concentration Risk Management | 2026-06-17 | 2026-07-01 | 50/52 | 2 | 43 | 4 |
| Credit Risk Management | 2026-06-14 | 2026-07-01 | 1/1 | 0 | 0 | 0 |
| Credit Information Reporting | - | - | - | - | - | no dated amendment markers |
| Credit Facilities | 2026-06-14 | 2026-06-23, 2026-07-01, 2026-07-15 | 158/159 | 1 | 56 | 2 |
| Interest Rate on Deposits | 2026-06-15 | 2026-06-17, 2026-08-25 | 2/2 | 0 | 0 | 0 |
| Prudential Norms on Capital Adequacy | - | - | - | - | - | no dated amendment markers |
| Cash Reserve Ratio and Statutory Liquidity Ratio | 2026-06-16 | 2026-06-19, 2026-08-25 | 3/3 | 0 | 0 | 0 |
| Undertaking of Financial Services | 2026-06-09 | 2026-07-01 | 2/2 | 0 | 0 | 0 |

**Total:** 262/266 RBI-amended clauses found; the 4 not found are marker-only (4: the marked paragraph's own text is unchanged) or listed below; 14 reported changes are not under any RBI marker.

- Responsible Business Conduct: found ['121A', '121B', '121C', '121D']; marker only, text unchanged ['121']
- Resolution of Stressed Assets: found ['103', '124A', '124B', '124C', '124D', '124E', '124F', '124G', '124H', '124I', '124J', '124K', '124L', '124M', '124N', '124O', '124P', '124Q', '124R', '124S', '124T', '124U', '124V', '124W', '124X', '13', '13(1)', '13(2)', '13(3)', '6(3)(v)', '6(8)']; extra not under a marked clause ['64', '77(5)']
- Income Recognition, Asset Classification and Provisioning: found ['139', '139B', '57(4)', '62(3)', '62B', '80(6)', '84', '84A', '84B', '84C', '84D']; extra not under a marked clause ['109(2)', '109(3)', '109(4)', '109(5)', '80(7)', 'U1']
- Concentration Risk Management: found ['100', '101', '101A', '101A(1)', '101A(10)', '101A(2)', '101A(3)', '101A(4)', '101A(5)', '101A(6)', '101A(7)', '101A(8)', '101A(9)', '102', '103', '104', '105', '106', '107', '107A', '107A(1)', '107A(2)', '107A(3)', '107A(4)', '107A(4)(i)', '107A(4)(ii)', '107B', '109', '95', '95A', '95A(1)', '95A(2)', '95A(2)(i)', '95A(2)(ii)', '95A(2)(iii)', '95A(2)(iv)', '95A(2)(ix)', '95A(2)(v)', '95A(2)(vi)', '95A(2)(vii)', '95A(2)(viii)', '95A(2)(x)', '97', '98', '98A', '98A(1)', '98A(2)', '98A(3)', '98A(4)', '99']; marker only, text unchanged ['5', '7']; extra not under a marked clause ['63(1)', 'U3', 'U5', 'U6']
- Credit Risk Management: found ['12A']
- Credit Facilities: found ['137', '137A(4)', '158', '159', '160', '161', '162', '163', '164', '165', '166', '167', '168', '169', '170', '170A', '170B', '170C', '170D', '170E', '170E(1)', '170E(2)', '170E(3)', '170E(4)', '170E(4)(a)', '170E(4)(b)', '170F', '170F(1)', '170G', '170G(i)', '170G(i)~2', '170G(ii)', '170G(ii)~2', '170G(ii)~2(2)', '170H', '170I', '170I(1)', '170I(2)', '170J', '170J(i)', '170J(ii)', '170J(ii)(a)', '170J(ii)(b)', '170J(ii)(c)', '170K', '170L', '170L(3)', '170M', '170N', '170N(4)', '170O', '170O(i)', '170O(ii)', '170P', '170Q', '170R', '170S', '176', '177', '178', '179', '180', '181', '182', '183', '184', '185', '186', '187', '188', '189', '190', '191', '192', '193', '194', '195', '196', '197', '198', '199', '200', '201', '202', '203', '204', '205', '206', '207', '208', '209', '210', '211', '212', '213', '214', '217', '219', '219A', '219B', '219B(1)', '219B(2)', '219B(3)', '219B(4)', '219B(5)', '219B(6)', '219B(7)', '219C', '219C(1)', '219C(2)', '219C(3)', '219C(4)', '219C(5)', '219C(6)', '219C(7)', '219D', '219E', '219F', '219G', '219H', '219I', '219I(1)', '219I(2)', '219J', '219K', '219L', '219M', '219N', '219O', '219P', '219Q', '219R', '219R(1)', '219R(2)', '219S', '219T', '219U', '219V', '219W', '219X', '219X(1)', '219X(2)', '219Y', '219Z', '219Z(1)', '219Z(2)', '219Z(3)', '5(11)', '5(13)', '5(14)', '5(16)', '5(6)', '5A', '5B', '5C', '78', '80(3)', 'U11']; marker only, text unchanged ['5']; extra not under a marked clause ['96(2)', 'U1']
- Interest Rate on Deposits: found ['27(4)', '32(7)']
- Cash Reserve Ratio and Statutory Liquidity Ratio: found ['20(8)', '20(9)', '29(5)']
- Undertaking of Financial Services: found ['18(4)(ii)(a)', '18(4)(ii)(b)']

Reading the extras (checked 27 Sep): some are real edits RBI did not mark with a date
(renumbered cross-references such as 'paragraph 36' -> 'paragraph 39', '(1)-(6)' ->
'(1)-(5)', '[***]' deletions), which marker-based ground truth cannot credit. The rest
expose two parser gaps the KYC corpus never exercised: inserted paragraphs numbered
'5A.' / '121A.' and sub-clauses '(ia)' are not recognised (they become unnumbered 'U'
clauses; this is also the one miss), and unnumbered clauses are aligned by position, so
one insertion shifts every later 'U' clause.
