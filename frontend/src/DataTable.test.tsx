// @vitest-environment jsdom
import React from 'react';
import {it,expect,afterEach} from 'vitest';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {DataTable} from './DataTable';
afterEach(cleanup);
it('paginates database rows and resets pagination when filtering',()=>{
 const rows=Array.from({length:12},(_,i)=>({id:i+1,name:`Product ${i+1}`}));
 render(<DataTable rows={rows} columns={ [['name','Product']] }/>);
 expect(screen.queryByText('Product 11')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Next'}));
 expect(screen.getByText('Product 11')).toBeTruthy();
 fireEvent.change(screen.getByRole('textbox',{name:'Search records'}),{target:{value:'Product 2'}});
 expect(screen.getByText('Product 2')).toBeTruthy();
 expect(screen.queryByText('Product 11')).toBeNull();
 expect(screen.getByText('Page 1 of 1')).toBeTruthy();
});
