# Change detection on real 2026 amendments of other RBI Directions

Old = latest Wayback capture before the amendments; new = current rbi.org.in page.
Ground truth = clauses RBI marked as amended after the old capture. Counts only; no
language model involved. KYC (2 amendments) is in change_detection.md.

| Direction | Old capture | Amendments (effective) | Found | Missed | Extra | Extra not under a marked clause |
|---|---|---|---|---|---|---|
| Responsible Business Conduct | 2026-06-15 | 2026-07-01 | 0/1 | 1 | 1 | 1 |
| Financial Statements: Presentation and Disclosures | - | - | - | - | - | no dated amendment markers |
| Resolution of Stressed Assets | 2026-06-14 | 2026-07-01 | 3/3 | 0 | 13 | 10 |
| Income Recognition, Asset Classification and Provisioning | 2026-06-17 | 2026-07-01 | 5/5 | 0 | 6 | 6 |
| Classification, Valuation and Operation of Investment Portfolio | - | - | - | - | - | no dated amendment markers |
| Concentration Risk Management | 2026-06-17 | 2026-07-01 | 7/7 | 0 | 70 | 29 |
| Credit Risk Management | 2026-06-14 | 2026-07-01 | 1/1 | 0 | 0 | 0 |
| Credit Information Reporting | - | - | - | - | - | no dated amendment markers |
| Credit Facilities | 2026-06-14 | 2026-06-23, 2026-07-01, 2026-07-15 | 11/11 | 0 | 165 | 128 |
| Interest Rate on Deposits | 2026-06-15 | 2026-06-17, 2026-08-25 | 2/2 | 0 | 0 | 0 |
| Prudential Norms on Capital Adequacy | - | - | - | - | - | no dated amendment markers |
| Cash Reserve Ratio and Statutory Liquidity Ratio | 2026-06-16 | 2026-06-19, 2026-08-25 | 3/3 | 0 | 0 | 0 |
| Undertaking of Financial Services | 2026-06-09 | 2026-07-01 | 2/2 | 0 | 0 | 0 |

- Responsible Business Conduct: found []; missed ['121']; extra not under a marked clause ['U10']
- Resolution of Stressed Assets: found ['13', '6(3)(v)', '6(8)']; extra not under a marked clause ['103', '64', '77(5)', 'U1', 'U2', 'U3', 'U4', 'U5', 'U6', 'U7']
- Income Recognition, Asset Classification and Provisioning: found ['139', '57(4)', '62(3)', '80(6)', '84']; extra not under a marked clause ['109(2)', '109(3)', '109(4)', '109(5)', '80(7)', 'U1']
- Concentration Risk Management: found ['100', '101', '102', '107', '95', '98', '99']; extra not under a marked clause ['103', '104', '105', '105(1)', '105(1)(i)', '105(1)(ii)', '105(1)(iii)', '105(1)(iv)', '105(1)(v)', '105(2)', '105(2)(i)', '105(2)(ii)', '105(2)(iii)', '105(2)(iv)', '106', '109', '109(1)', '109(2)', '109(3)', '109(4)', '109(5)', '109(6)', '109(7)', '109(8)', '63(1)', '97', 'U3', 'U5', 'U6']
- Credit Risk Management: found ['12']
- Credit Facilities: found ['137', '137(4)', '170', '219', '5(11)', '5(13)', '5(14)', '5(16)', '5(6)', '78', '80(3)']; extra not under a marked clause ['158', '158(1)', '158(2)', '158(3)', '158(4)', '159', '160', '160(1)', '160(1)(i)', '160(1)(ii)', '160(2)', '160(2)(i)', '160(2)(ii)', '161', '162', '163', '163(1)', '163(2)', '163(3)', '163(4)', '164', '165', '166', '166(1)', '166(2)', '166(3)', '166(4)', '166(5)', '167', '168', '169', '176', '177', '178', '179', '180', '181', '182', '183', '184', '185', '186', '187', '187(1)', '187(2)', '187(3)', '187(4)', '187(5)', '187(6)', '187(7)', '188', '188(1)', '188(2)', '188(3)', '188(4)', '188(5)', '188(6)', '188(7)', '188(8)', '189', '190', '191', '192', '193', '194', '195', '196', '197', '197(1)', '197(2)', '197(3)', '197(4)', '197(5)', '198', '198(1)', '198(2)', '198(3)', '198(4)', '199', '200', '201', '202', '203', '204', '205', '206', '207', '208', '209', '210', '211', '212', '213', '214', '217', '5(15)', '96(2)', 'U1', 'U10', 'U11', 'U12', 'U13', 'U14', 'U15', 'U16', 'U17', 'U18', 'U19', 'U2', 'U20', 'U21', 'U22', 'U23', 'U24', 'U25', 'U26', 'U27', 'U28', 'U29', 'U3', 'U30', 'U31', 'U4', 'U5', 'U6', 'U7', 'U8', 'U9']
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
