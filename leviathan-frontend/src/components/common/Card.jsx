import React from 'react';
import '../../styles/index.css';

const Card = ({
  children,
  className = '',
  header,
  footer,
  hoverable = false,
  ...props
}) => {
  return (
    <div 
      className={`card ${hoverable ? 'hoverable' : ''} ${className}`}
      {...props}
    >
      {header && <div className="card-header">{header}</div>}
      <div className="card-body">{children}</div>
      {footer && <div className="card-footer">{footer}</div>}
    </div>
  );
};

export default Card;
