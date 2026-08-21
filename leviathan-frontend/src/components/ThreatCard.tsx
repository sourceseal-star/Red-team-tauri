import React from 'react'

interface ThreatCardProps {
  score: number
  level: string
  factors: { name: string; weight: number; value: number }[]
}

const ThreatCard: React.FC<ThreatCardProps> = ({ score, level, factors }) => {
  const color = score >= 75 ? '#dc3545' : score >= 50 ? '#ffc107' : '#28a745'
  return (
    <div className="threat-card">
      <div className="threat-score" style={{ color }}>
        <span className="score-number">{score}</span>
        <span className="score-level">{level}</span>
      </div>
      <div className="threat-factors">
        {factors.map(f => (
          <div key={f.name} className="factor-row">
            <span className="factor-name">{f.name}</span>
            <div className="factor-bar-bg">
              <div className="factor-bar" style={{ width: `${f.value}%`, backgroundColor: color }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default ThreatCard
