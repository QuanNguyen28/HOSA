import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { HorizonMarker } from './HorizonMarker';

describe('Horizon visibility symbols', () => {
  it('draws a hidden body as a dashed outline without filling its disc', () => {
    const html=renderToStaticMarkup(<svg><HorizonMarker x={10} y={20} colour="#ffc62b" state="hidden"/></svg>);
    expect(html).toContain('fill="none"'); expect(html).toContain('stroke-dasharray="3 2"');
    expect(html).toContain('stroke="#ffc62b"');
  });
  it('keeps a visible disc filled and distinguishes unknown evidence from hidden', () => {
    const render=(state:'visible'|'unknown')=>renderToStaticMarkup(<svg><HorizonMarker x={0} y={0} colour="#47afe8" state={state}/></svg>);
    expect(render('visible')).toContain('fill="#47afe8"');
    expect(render('visible')).not.toContain('stroke-dasharray');
    expect(render('unknown')).toContain('stroke-dasharray="1 3"');
  });
});
