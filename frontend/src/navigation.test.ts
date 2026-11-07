import {describe,it,expect} from 'vitest';
import {groups,slug} from './navigation';
describe('Operational navigation',()=>{it('exposes all 51 uniquely addressable pages',()=>{const pages=Object.values(groups).flat();expect(pages).toHaveLength(51);expect(new Set(pages.map(slug)).size).toBe(51)})});
