from dataclasses import dataclass, field
from typing import Dict, Optional
import uuid

# pip install reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)


@dataclass
class Member:
    wallet: str
    tokens: float
    delegated_to: Optional[str] = None

    def voting_power(self, members: Dict[str, "Member"]) -> float:
        if self.delegated_to is not None:
            return 0.0

        power = self.tokens
        for member in members.values():
            if member.delegated_to == self.wallet:
                power += member.tokens
        return power


@dataclass
class Proposal:
    id: str
    title: str
    description: str
    proposer: str
    quorum_required_pct: float
    pass_threshold_pct: float
    status: str = "Active"
    votes_for: float = 0.0
    votes_against: float = 0.0
    voters: Dict[str, str] = field(default_factory=dict)

    def total_votes(self) -> float:
        return self.votes_for + self.votes_against

    def approval_pct(self) -> float:
        total = self.total_votes()
        if total == 0:
            return 0.0
        return (self.votes_for / total) * 100


class DAOGovernanceEngine:
    def __init__(self):
        self.members: Dict[str, Member] = {}
        self.proposals: Dict[str, Proposal] = {}

    def add_member(self, wallet: str, tokens: float):
        if wallet in self.members:
            raise ValueError(f"Wallet {wallet} already exists.")
        self.members[wallet] = Member(wallet=wallet, tokens=tokens)

    def delegate_votes(self, from_wallet: str, to_wallet: str):
        if from_wallet not in self.members or to_wallet not in self.members:
            raise ValueError("Both wallets must exist.")
        if from_wallet == to_wallet:
            raise ValueError("Cannot delegate to self.")
        if self.members[from_wallet].delegated_to is not None:
            raise ValueError(f"{from_wallet} has already delegated their votes.")
        self.members[from_wallet].delegated_to = to_wallet

    def create_proposal(
        self,
        proposer: str,
        title: str,
        description: str,
        quorum_required_pct: float = 30.0,
        pass_threshold_pct: float = 50.0
    ) -> str:
        if proposer not in self.members:
            raise ValueError("Proposer must be a DAO member.")

        proposal_id = str(uuid.uuid4())[:8]
        proposal = Proposal(
            id=proposal_id,
            title=title,
            description=description,
            proposer=proposer,
            quorum_required_pct=quorum_required_pct,
            pass_threshold_pct=pass_threshold_pct
        )
        self.proposals[proposal_id] = proposal
        return proposal_id

    def cast_vote(self, proposal_id: str, wallet: str, vote: str):
        if proposal_id not in self.proposals:
            raise ValueError("Proposal not found.")
        if wallet not in self.members:
            raise ValueError("Wallet not found.")
        if vote not in ["FOR", "AGAINST"]:
            raise ValueError("Vote must be 'FOR' or 'AGAINST'.")

        proposal = self.proposals[proposal_id]
        member = self.members[wallet]

        if proposal.status != "Active":
            raise ValueError("Voting is closed for this proposal.")
        if member.delegated_to is not None:
            raise ValueError(f"{wallet} delegated voting power and cannot vote directly.")
        if wallet in proposal.voters:
            raise ValueError(f"{wallet} has already voted.")

        power = member.voting_power(self.members)

        if vote == "FOR":
            proposal.votes_for += power
        else:
            proposal.votes_against += power

        proposal.voters[wallet] = vote

    def finalize_proposal(self, proposal_id: str):
        if proposal_id not in self.proposals:
            raise ValueError("Proposal not found.")

        proposal = self.proposals[proposal_id]
        if proposal.status != "Active":
            raise ValueError("Proposal already finalized.")

        total_token_supply = sum(member.tokens for member in self.members.values())
        total_votes_cast = proposal.total_votes()

        quorum_pct = (total_votes_cast / total_token_supply) * 100 if total_token_supply > 0 else 0
        approval_pct = proposal.approval_pct()

        if quorum_pct < proposal.quorum_required_pct:
            proposal.status = "Failed - No Quorum"
        elif approval_pct >= proposal.pass_threshold_pct:
            proposal.status = "Passed"
        else:
            proposal.status = "Rejected"

    def get_whale_concentration(self) -> float:
        total_supply = sum(member.tokens for member in self.members.values())
        if total_supply == 0:
            return 0.0

        sorted_balances = sorted((m.tokens for m in self.members.values()), reverse=True)
        top_3 = sum(sorted_balances[:3])
        return round((top_3 / total_supply) * 100, 2)

    def get_rage_quit_risk(self) -> str:
        whale_concentration = self.get_whale_concentration()

        if whale_concentration >= 60:
            return "EXTREME"
        elif whale_concentration >= 40:
            return "HIGH"
        elif whale_concentration >= 25:
            return "MODERATE"
        return "LOW"

    def governance_health_report(self) -> Dict:
        total_supply = sum(member.tokens for member in self.members.values())
        delegated_supply = sum(
            member.tokens for member in self.members.values() if member.delegated_to is not None
        )
        active_voters = sum(1 for m in self.members.values() if m.delegated_to is None)

        return {
            "total_members": len(self.members),
            "total_token_supply": round(total_supply, 2),
            "delegated_token_supply": round(delegated_supply, 2),
            "active_voters": active_voters,
            "whale_concentration_pct_top_3": self.get_whale_concentration(),
            "rage_quit_risk": self.get_rage_quit_risk()
        }

    def proposal_summary(self, proposal_id: str) -> Dict:
        if proposal_id not in self.proposals:
            raise ValueError("Proposal not found.")

        proposal = self.proposals[proposal_id]
        total_supply = sum(member.tokens for member in self.members.values())
        quorum_pct = (proposal.total_votes() / total_supply) * 100 if total_supply > 0 else 0

        return {
            "proposal_id": proposal.id,
            "title": proposal.title,
            "proposer": proposal.proposer,
            "status": proposal.status,
            "votes_for": round(proposal.votes_for, 2),
            "votes_against": round(proposal.votes_against, 2),
            "total_votes": round(proposal.total_votes(), 2),
            "approval_pct": round(proposal.approval_pct(), 2),
            "quorum_pct": round(quorum_pct, 2),
            "unique_voters": len(proposal.voters)
        }

    def export_plain_english_pdf(self, proposal_id: str, filename: str = "dao_governance_report.pdf"):
        if proposal_id not in self.proposals:
            raise ValueError("Proposal not found.")

        proposal = self.proposals[proposal_id]
        health = self.governance_health_report()
        summary = self.proposal_summary(proposal_id)

        doc = SimpleDocTemplate(
            filename,
            pagesize=LETTER,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch
        )

        styles = getSampleStyleSheet()
        title_style = styles["Title"]
        heading_style = styles["Heading2"]
        body_style = ParagraphStyle(
            "BodyCustom",
            parent=styles["BodyText"],
            fontSize=10.5,
            leading=15,
            alignment=TA_LEFT,
            spaceAfter=8
        )
        small_style = ParagraphStyle(
            "SmallCustom",
            parent=styles["BodyText"],
            fontSize=9,
            leading=12
        )

        story = []

        story.append(Paragraph("DAO Governance Engine - Plain English Report", title_style))
        story.append(Spacer(1, 12))
        story.append(Paragraph(
            "This report explains the governance simulation in plain English so that non-technical readers can understand what happened, why it mattered, and what risks showed up in the DAO structure.",
            body_style
        ))
        story.append(Spacer(1, 6))

        story.append(Paragraph("1. What this project does", heading_style))
        story.append(Paragraph(
            "This Python project simulates how a DAO makes decisions. A DAO is an internet-based organization where token holders vote on proposals. Instead of a traditional CEO or board making every decision, voting power is distributed across wallets that hold tokens.",
            body_style
        ))
        story.append(Paragraph(
            "In simple terms: more tokens usually means more influence.",
            body_style
        ))

        story.append(Paragraph("2. What happened in this simulation", heading_style))
        plain_result = (
            f'The proposal titled "{proposal.title}" was submitted by {proposal.proposer}. '
            f'It finished with a status of "{summary["status"]}". '
            f'There were {summary["votes_for"]} votes in favor and {summary["votes_against"]} votes against. '
            f'The final approval rate was {summary["approval_pct"]}% and the proposal reached {summary["quorum_pct"]}% quorum.'
        )
        story.append(Paragraph(plain_result, body_style))

        story.append(Paragraph("3. Key concepts in plain English", heading_style))
        explanations = [
            ["Voting Power", "Each wallet gets influence based on how many governance tokens it holds."],
            ["Delegation", "A member can hand their voting power to another wallet, increasing that wallet's influence."],
            ["Quorum", "This is the minimum amount of participation required for a proposal to count."],
            ["Approval Rate", "This is the percentage of votes that supported the proposal."],
            ["Whale Concentration", "This shows how much power is controlled by the biggest token holders."],
            ["Rage Quit Risk", "This estimates whether smaller members may lose faith because too much power sits with a few wallets."]
        ]

        concept_table = Table(explanations, colWidths=[1.75 * inch, 4.75 * inch])
        concept_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.grey),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("LEADING", (0, 0), (-1, -1), 12),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.append(concept_table)
        story.append(Spacer(1, 12))

        story.append(Paragraph("4. Governance health snapshot", heading_style))
        health_data = [
            ["Metric", "Value"],
            ["Total Members", str(health["total_members"])],
            ["Total Token Supply", f'{health["total_token_supply"]:,}'],
            ["Delegated Token Supply", f'{health["delegated_token_supply"]:,}'],
            ["Active Voters", str(health["active_voters"])],
            ["Top 3 Whale Concentration", f'{health["whale_concentration_pct_top_3"]}%'],
            ["Rage Quit Risk", health["rage_quit_risk"]],
        ]

        health_table = Table(health_data, colWidths=[2.5 * inch, 2.75 * inch])
        health_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.grey),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 1), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.append(health_table)
        story.append(Spacer(1, 12))

        story.append(Paragraph("5. What this means in plain English", heading_style))

        whale_pct = health["whale_concentration_pct_top_3"]
        risk = health["rage_quit_risk"]
        status = summary["status"]

        interpretation = []

        if whale_pct >= 60:
            interpretation.append(
                "A very small number of wallets control most of the governance power. That means this DAO may look decentralized on the surface, but in practice it can be pushed around by a few major holders."
            )
        elif whale_pct >= 40:
            interpretation.append(
                "The DAO has meaningful participation, but large wallets still have strong influence. This creates a real risk of governance capture."
            )
        else:
            interpretation.append(
                "Token ownership is relatively more distributed, which is healthier for governance and usually makes decision-making feel more legitimate."
            )

        if status == "Passed":
            interpretation.append(
                "This proposal passed, which means it cleared both participation requirements and support requirements."
            )
        elif status == "Failed - No Quorum":
            interpretation.append(
                "This proposal failed because not enough token holders participated. That is usually a sign of weak engagement, poor communication, or governance fatigue."
            )
        else:
            interpretation.append(
                "This proposal was rejected, meaning enough people participated but support was not strong enough to pass it."
            )

        if risk == "EXTREME":
            interpretation.append(
                "Rage quit risk is extreme. Smaller members may begin to feel that governance is performative rather than real."
            )
        elif risk == "HIGH":
            interpretation.append(
                "Rage quit risk is high. If the same wallets dominate repeatedly, community trust can erode fast."
            )
        else:
            interpretation.append(
                "Governance risk is not negligible, but the DAO still has a healthier chance of maintaining trust among members."
            )

        for paragraph in interpretation:
            story.append(Paragraph(paragraph, body_style))

        story.append(PageBreak())

        story.append(Paragraph("6. Proposal summary", heading_style))
        proposal_data = [
            ["Field", "Value"],
            ["Proposal ID", str(summary["proposal_id"])],
            ["Title", str(summary["title"])],
            ["Proposer", str(summary["proposer"])],
            ["Status", str(summary["status"])],
            ["Votes For", str(summary["votes_for"])],
            ["Votes Against", str(summary["votes_against"])],
            ["Total Votes", str(summary["total_votes"])],
            ["Approval %", f'{summary["approval_pct"]}%'],
            ["Quorum %", f'{summary["quorum_pct"]}%'],
            ["Unique Voters", str(summary["unique_voters"])],
        ]

        proposal_table = Table(proposal_data, colWidths=[2.2 * inch, 3.2 * inch])
        proposal_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.grey),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 1), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.append(proposal_table)
        story.append(Spacer(1, 12))

        story.append(Paragraph("7. Why this project is useful", heading_style))
        story.append(Paragraph(
            "This kind of project helps explain a major truth about DAOs: governance is not just a voting interface. It is a power structure. The real question is not whether votes happen, but who actually has enough weight to decide outcomes when it matters.",
            body_style
        ))
        story.append(Paragraph(
            "That makes this project useful not only for developers, but also for founders, operators, treasury managers, and anyone trying to understand whether a DAO is genuinely decentralized or just pretending to be.",
            body_style
        ))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "Generated automatically by the DAO Governance Engine.",
            small_style
        ))

        doc.build(story)
        print(f"Plain English PDF exported successfully: {filename}")


def print_section(title: str):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


if __name__ == "__main__":
    dao = DAOGovernanceEngine()

    dao.add_member("0xAlpha", 40000)
    dao.add_member("0xBravo", 22000)
    dao.add_member("0xCharlie", 18000)
    dao.add_member("0xDelta", 9000)
    dao.add_member("0xEcho", 6500)
    dao.add_member("0xFoxtrot", 4500)
    dao.add_member("0xGamma", 3000)
    dao.add_member("0xHotel", 2000)

    dao.delegate_votes("0xGamma", "0xCharlie")
    dao.delegate_votes("0xHotel", "0xCharlie")

    print_section("DAO GOVERNANCE HEALTH REPORT")
    health = dao.governance_health_report()
    for k, v in health.items():
        print(f"{k}: {v}")

    proposal_id = dao.create_proposal(
        proposer="0xAlpha",
        title="Deploy 500k USDC into LSD Yield Strategy",
        description="Allocate idle treasury reserves into a low-risk liquid staking strategy.",
        quorum_required_pct=35.0,
        pass_threshold_pct=55.0
    )

    print_section(f"NEW PROPOSAL CREATED: {proposal_id}")
    print(dao.proposal_summary(proposal_id))

    dao.cast_vote(proposal_id, "0xAlpha", "FOR")
    dao.cast_vote(proposal_id, "0xBravo", "AGAINST")
    dao.cast_vote(proposal_id, "0xCharlie", "FOR")
    dao.cast_vote(proposal_id, "0xDelta", "FOR")
    dao.cast_vote(proposal_id, "0xEcho", "AGAINST")
    dao.cast_vote(proposal_id, "0xFoxtrot", "FOR")

    print_section("PROPOSAL STATE BEFORE FINALIZATION")
    print(dao.proposal_summary(proposal_id))

    dao.finalize_proposal(proposal_id)

    print_section("FINAL PROPOSAL RESULT")
    print(dao.proposal_summary(proposal_id))

    # Auto-generate plain English PDF
    dao.export_plain_english_pdf(
        proposal_id=proposal_id,
        filename="dao_governance_plain_english_report.pdf"
    )