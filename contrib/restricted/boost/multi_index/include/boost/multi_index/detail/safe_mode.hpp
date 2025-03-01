/* Copyright 2003-2023 Joaquin M Lopez Munoz.
 * Distributed under the Boost Software License, Version 1.0.
 * (See accompanying file LICENSE_1_0.txt or copy at
 * http://www.boost.org/LICENSE_1_0.txt)
 *
 * See http://www.boost.org/libs/multi_index for library home page.
 */

#ifndef BOOST_MULTI_INDEX_DETAIL_SAFE_MODE_HPP
#define BOOST_MULTI_INDEX_DETAIL_SAFE_MODE_HPP

#if defined(_MSC_VER)
#pragma once
#endif

/* Safe mode machinery, in the spirit of Cay Hortmann's "Safe STL"
 * (http://www.horstmann.com/safestl.html).
 * In this mode, containers have to redefine their iterators as
 * safe_iterator<base_iterator> and keep a tracking object member of
 * type safe_container<safe_iterator<base_iterator> >. These classes provide
 * an internal record of which iterators are at a given moment associated
 * to a given container, and properly mark the iterators as invalid
 * when the container gets destroyed.
 * Iterators are chained in a single attached list, whose header is
 * kept by the container. More elaborate data structures would yield better
 * performance, but I decided to keep complexity to a minimum since
 * speed is not an issue here.
 * Safe mode iterators automatically check that only proper operations
 * are performed on them: for instance, an invalid iterator cannot be
 * dereferenced. Additionally, a set of utilty macros and functions are
 * provided that serve to implement preconditions and cooperate with
 * the framework within the container.
 * Iterators can also be unchecked, i.e. they do not have info about
 * which container they belong in. This situation arises when the iterator
 * is restored from a serialization archive: only information on the node
 * is available, and it is not possible to determine to which container
 * the iterator is associated to. The only sensible policy is to assume
 * unchecked iterators are valid, though this can certainly generate false
 * positive safe mode checks.
 * This is not a full-fledged safe mode framework, and is only intended
 * for use within the limits of Boost.MultiIndex.
 */

/* Assertion macros. These resolve to no-ops if
 * !defined(BOOST_MULTI_INDEX_ENABLE_SAFE_MODE).
 */

#if !defined(BOOST_MULTI_INDEX_ENABLE_SAFE_MODE)
#undef BOOST_MULTI_INDEX_SAFE_MODE_ASSERT
#define BOOST_MULTI_INDEX_SAFE_MODE_ASSERT(expr,error_code) ((void)0)
#else
#if !defined(BOOST_MULTI_INDEX_SAFE_MODE_ASSERT)
#include <boost/assert.hpp>
#define BOOST_MULTI_INDEX_SAFE_MODE_ASSERT(expr,error_code) BOOST_ASSERT(expr)
#endif
#endif

#define BOOST_MULTI_INDEX_CHECK_VALID_ITERATOR(it)                           \
  BOOST_MULTI_INDEX_SAFE_MODE_ASSERT(                                        \
    safe_mode::check_valid_iterator(it),                                     \
    safe_mode::invalid_iterator);

#define BOOST_MULTI_INDEX_CHECK_DEREFERENCEABLE_ITERATOR(it)                 \
  BOOST_MULTI_INDEX_SAFE_MODE_ASSERT(                                        \
    safe_mode::check_dereferenceable_iterator(it),                           \
    safe_mode::not_dereferenceable_iterator);

#define BOOST_MULTI_INDEX_CHECK_INCREMENTABLE_ITERATOR(it)                   \
  BOOST_MULTI_INDEX_SAFE_MODE_ASSERT(                                        \
    safe_mode::check_incrementable_iterator(it),                             \
    safe_mode::not_incrementable_iterator);

#define BOOST_MULTI_INDEX_CHECK_DECREMENTABLE_ITERATOR(it)                   \
  BOOST_MULTI_INDEX_SAFE_MODE_ASSERT(                                        \
    safe_mode::check_decrementable_iterator(it),                             \
    safe_mode::not_decrementable_iterator);

#define BOOST_MULTI_INDEX_CHECK_IS_OWNER(it,cont)                            \
  BOOST_MULTI_INDEX_SAFE_MODE_ASSERT(                                        \
    safe_mode::check_is_owner(it,cont),                                      \
    safe_mode::not_owner);

#define BOOST_MULTI_INDEX_CHECK_BELONGS_IN_SOME_INDEX(it,cont)               \
  BOOST_MULTI_INDEX_SAFE_MODE_ASSERT(                                        \
    safe_mode::check_belongs_in_some_index(it,cont),                         \
    safe_mode::not_owner);

#define BOOST_MULTI_INDEX_CHECK_SAME_OWNER(it0,it1)                          \
  BOOST_MULTI_INDEX_SAFE_MODE_ASSERT(                                        \
    safe_mode::check_same_owner(it0,it1),                                    \
    safe_mode::not_same_owner);

#define BOOST_MULTI_INDEX_CHECK_VALID_RANGE(it0,it1)                         \
  BOOST_MULTI_INDEX_SAFE_MODE_ASSERT(                                        \
    safe_mode::check_valid_range(it0,it1),                                   \
    safe_mode::invalid_range);

#define BOOST_MULTI_INDEX_CHECK_OUTSIDE_RANGE(it,it0,it1)                    \
  BOOST_MULTI_INDEX_SAFE_MODE_ASSERT(                                        \
    safe_mode::check_outside_range(it,it0,it1),                              \
    safe_mode::inside_range);

#define BOOST_MULTI_INDEX_CHECK_IN_BOUNDS(it,n)                              \
  BOOST_MULTI_INDEX_SAFE_MODE_ASSERT(                                        \
    safe_mode::check_in_bounds(it,n),                                        \
    safe_mode::out_of_bounds);

#define BOOST_MULTI_INDEX_CHECK_DIFFERENT_CONTAINER(cont0,cont1)             \
  BOOST_MULTI_INDEX_SAFE_MODE_ASSERT(                                        \
    safe_mode::check_different_container(cont0,cont1),                       \
    safe_mode::same_container);

#define BOOST_MULTI_INDEX_CHECK_EQUAL_ALLOCATORS(cont0,cont1)                 \
  BOOST_MULTI_INDEX_SAFE_MODE_ASSERT(                                        \
    safe_mode::check_equal_allocators(cont0,cont1),                           \
    safe_mode::unequal_allocators);

#if defined(BOOST_MULTI_INDEX_ENABLE_SAFE_MODE)
#include <boost/config.hpp> /* keep it first to prevent nasty warns in MSVC */
#include <algorithm>
#include <boost/core/addressof.hpp>
#include <boost/core/noncopyable.hpp>
#include <boost/multi_index/detail/access_specifier.hpp>
#include <boost/multi_index/detail/any_container_view.hpp>
#include <boost/multi_index/detail/iter_adaptor.hpp>
#include <boost/multi_index/safe_mode_errors.hpp>
#include <boost/type_traits/is_same.hpp>

#if !defined(BOOST_MULTI_INDEX_DISABLE_SERIALIZATION)
#include <boost/core/serialization.hpp>
#endif

#if defined(BOOST_HAS_THREADS)
#include <boost/smart_ptr/detail/lightweight_mutex.hpp>
#include <boost/multi_index/detail/scoped_bilock.hpp>
#endif

namespace boost{

namespace multi_index{

namespace safe_mode{

/* Checking routines. Assume the best for unchecked iterators
 * (i.e. they pass the checking when there is not enough info
 * to know.)
 */

template<typename Iterator>
inline bool check_valid_iterator(const Iterator& it)
{
  return it.valid()||it.unchecked();
}

template<typename Iterator>
inline bool check_dereferenceable_iterator(const Iterator& it)
{
  return (it.valid()&&it!=it.owner()->end())||it.unchecked();
}

template<typename Iterator>
inline bool check_incrementable_iterator(const Iterator& it)
{
  return (it.valid()&&it!=it.owner()->end())||it.unchecked();
}

template<typename Iterator>
inline bool check_decrementable_iterator(const Iterator& it)
{
  return (it.valid()&&it!=it.owner()->begin())||it.unchecked();
}

template<typename Iterator,typename Container>
inline bool check_is_owner(
  const Iterator& it,const Container& cont)
{
  return (it.valid()&&
            it.owner()->container()==cont.end().owner()->container())
         ||it.unchecked();
}

template<typename Iterator,typename MultiIndexContainer>
inline bool check_belongs_in_some_index(
  const Iterator& it,const MultiIndexContainer& cont)
{
  return (it.valid()&&it.owner()->end().get_node()==cont.end().get_node())
         ||it.unchecked();
} 

template<typename Iterator>
inline bool check_same_owner(const Iterator& it0,const Iterator& it1)
{
  return (it0.valid()&&it1.valid()&&
            it0.owner()->container()==it1.owner()->container())
         ||it0.unchecked()||it1.unchecked();
}

template<typename Iterator>
inline bool check_valid_range(const Iterator& it0,const Iterator& it1)
{
  if(!check_same_owner(it0,it1))return false;

  if(it0.valid()){
    Iterator last=it0.owner()->end();
    if(it1==last)return true;

    for(Iterator first=it0;first!=last;++first){
      if(first==it1)return true;
    }
    return false;
  }
  return true;
}

template<typename Iterator>
inline bool check_outside_range(
  const Iterator& it,const Iterator& it0,const Iterator& it1)
{
  if(!check_same_owner(it0,it1))return false;

  if(it0.valid()){
    Iterator last=it0.owner()->end();
    bool found=false;

    Iterator first=it0;
    for(;first!=last;++first){
      if(first==it1)break;
    
      /* crucial that this check goes after previous break */
    
      if(first==it)found=true;
    }
    if(first!=it1)return false;
    return !found;
  }
  return true;
}

template<typename Iterator1,typename Iterator2>
inline bool check_outside_range(
  const Iterator1& it,const Iterator2& it0,const Iterator2& it1)
{
  if(it.valid()&&it!=it.owner()->end()&&it0.valid()){
    Iterator2 last=it0.owner()->end();
    bool found=false;

    Iterator2 first=it0;
    for(;first!=last;++first){
      if(first==it1)break;
    
      /* crucial that this check goes after previous break */
    
      if(boost::addressof(*first)==boost::addressof(*it))found=true;
    }
    if(first!=it1)return false;
    return !found;
  }
  return true;
}

template<typename Iterator,typename Difference>
inline bool check_in_bounds(const Iterator& it,Difference n)
{
  if(it.unchecked())return true;
  if(!it.valid())   return false;
  if(n>0)           return it.owner()->end()-it>=n;
  else              return it.owner()->begin()-it<=n;
}

template<typename Container>
inline bool check_different_container(
  const Container& cont0,const Container& cont1)
{
  return &cont0!=&cont1;
}

template<typename Container1,typename Container2>
inline bool check_different_container(const Container1&,const Container2&)
{
  return true;
}

template<typename Container0,typename Container1>
inline bool check_equal_allocators(
  const Container0& cont0,const Container1& cont1)
{
  return cont0.get_allocator()==cont1.get_allocator();
}

/* fwd decls */

template<typename Container> class safe_container;
template<typename Iterator> void detach_equivalent_iterators(Iterator&);

namespace safe_mode_detail{

/* fwd decls */

class safe_container_base;
template<typename Dst,typename Iterator>
void transfer_equivalent_iterators(Dst&,Iterator,boost::true_type);
template<typename Dst,typename Iterator>
inline void transfer_equivalent_iterators(Dst&,Iterator&,boost::false_type);

class safe_iterator_base
{
public:
  bool valid()const{return cont!=0;}
  bool unchecked()const{return unchecked_;}

  inline void detach();

  void uncheck()
  {
    detach();
    unchecked_=true;
  }

protected:
  safe_iterator_base():cont(0),next(0),unchecked_(false){}

  explicit safe_iterator_base(safe_container_base* cont_):
    unchecked_(false)
  {
    attach(cont_);
  }

  safe_iterator_base(const safe_iterator_base& it):
    unchecked_(it.unchecked_)
  {
    attach(it.cont);
  }

  safe_iterator_base& operator=(const safe_iterator_base& it)
  {
    unchecked_=it.unchecked_;
    safe_container_base* new_cont=it.cont;
    if(cont!=new_cont){
      detach();
      attach(new_cont);
    }
    return *this;
  }

  ~safe_iterator_base()
  {
    detach();
  }

  const safe_container_base* owner()const{return cont;}

BOOST_MULTI_INDEX_PRIVATE_IF_MEMBER_TEMPLATE_FRIENDS:

#if !defined(BOOST_NO_MEMBER_TEMPLATE_FRIENDS)
  friend class safe_container_base;
  template<typename>
  friend class safe_mode::safe_container;
  template<typename Iterator>
  friend void safe_mode::detach_equivalent_iterators(Iterator&);
  template<typename Dst,typename Iterator>
  friend void safe_mode_detail::transfer_equivalent_iterators(
    Dst&,Iterator,boost::true_type);
#endif

  inline void attach(safe_container_base* cont_);

  safe_container_base* cont;
  safe_iterator_base*  next;
  bool                 unchecked_;
};

class safe_container_base:private noncopyable
{
public:
  safe_container_base(){}

BOOST_MULTI_INDEX_PROTECTED_IF_MEMBER_TEMPLATE_FRIENDS:

#if !defined(BOOST_NO_MEMBER_TEMPLATE_FRIENDS)
  friend class safe_iterator_base;
  template<typename Iterator>
  friend void safe_mode::detach_equivalent_iterators(Iterator&);
  template<typename Dst,typename Iterator>
  friend void safe_mode_detail::transfer_equivalent_iterators(
    Dst&,Iterator,boost::true_type);
#endif

  ~safe_container_base()
  {
    /* Detaches all remaining iterators, which by now will
     * be those pointing to the end of the container.
     */

    for(safe_iterator_base* it=header.next;it;it=it->next)it->cont=0;
    header.next=0;
  }

  void swap(safe_container_base& x)
  {
    for(safe_iterator_base* it0=header.next;it0;it0=it0->next)it0->cont=&x;
    for(safe_iterator_base* it1=x.header.next;it1;it1=it1->next)it1->cont=this;
    std::swap(header.cont,x.header.cont);
    std::swap(header.next,x.header.next);
  }

  safe_iterator_base header;

#if defined(BOOST_HAS_THREADS)
  boost::detail::lightweight_mutex mutex;
#endif
};

void safe_iterator_base::attach(safe_container_base* cont_)
{
  cont=cont_;
  if(cont){
#if defined(BOOST_HAS_THREADS)
    boost::detail::lightweight_mutex::scoped_lock lock(cont->mutex);
#endif

    next=cont->header.next;
    cont->header.next=this;
  }
}

void safe_iterator_base::detach()
{
  if(cont){
#if defined(BOOST_HAS_THREADS)
    boost::detail::lightweight_mutex::scoped_lock lock(cont->mutex);
#endif

    safe_iterator_base *prev_,*next_;
    for(prev_=&cont->header;(next_=prev_->next)!=this;prev_=next_){}
    prev_->next=next;
    cont=0;
  }
}

} /* namespace multi_index::safe_mode::safe_mode_detail */

/* In order to enable safe mode on a container:
 *   - The container must keep a member of type safe_container<iterator>,
 *   - iterators must be generated via safe_iterator, which adapts a
 *     preexistent unsafe iterator class. safe_iterators are passed the
 *     address of the previous safe_container member at construction time.
 */
 
template<typename Iterator>
class safe_iterator:
  public detail::iter_adaptor<safe_iterator<Iterator>,Iterator>,
  public safe_mode_detail::safe_iterator_base
{
  typedef detail::iter_adaptor<safe_iterator,Iterator> super;
  typedef safe_mode_detail::safe_iterator_base         safe_super;

public:
  typedef typename Iterator::reference                 reference;
  typedef typename Iterator::difference_type           difference_type;

  safe_iterator(){}
  explicit safe_iterator(safe_container<safe_iterator>* cont_):
    safe_super(cont_){}
  template<typename T0>
  safe_iterator(const T0& t0,safe_container<safe_iterator>* cont_):
    super(Iterator(t0)),safe_super(cont_){}
  template<typename T0,typename T1>
  safe_iterator(
    const T0& t0,const T1& t1,safe_container<safe_iterator>* cont_):
    super(Iterator(t0,t1)),safe_super(cont_){}
  safe_iterator(const safe_iterator& x):super(x),safe_super(x){}

  safe_iterator& operator=(const safe_iterator& x)
  {
    BOOST_MULTI_INDEX_CHECK_VALID_ITERATOR(x);
    this->base_reference()=x.base_reference();
    safe_super::operator=(x);
    return *this;
  }

  const safe_container<safe_iterator>* owner()const
  {
    return
      static_cast<const safe_container<safe_iterator>*>(
        this->safe_super::owner());
  }

  /* get_node is not to be used by the user */

  typedef typename Iterator::node_type node_type;

  node_type* get_node()const{return this->base_reference().get_node();}

private:
  friend class boost::multi_index::detail::iter_adaptor_access;

  reference dereference()const
  {
    BOOST_MULTI_INDEX_CHECK_VALID_ITERATOR(*this);
    BOOST_MULTI_INDEX_CHECK_DEREFERENCEABLE_ITERATOR(*this);
    return *(this->base_reference());
  }

  bool equal(const safe_iterator& x)const
  {
    BOOST_MULTI_INDEX_CHECK_VALID_ITERATOR(*this);
    BOOST_MULTI_INDEX_CHECK_VALID_ITERATOR(x);
    BOOST_MULTI_INDEX_CHECK_SAME_OWNER(*this,x);
    return this->base_reference()==x.base_reference();
  }

  void increment()
  {
    BOOST_MULTI_INDEX_CHECK_VALID_ITERATOR(*this);
    BOOST_MULTI_INDEX_CHECK_INCREMENTABLE_ITERATOR(*this);
    ++(this->base_reference());
  }

  void decrement()
  {
    BOOST_MULTI_INDEX_CHECK_VALID_ITERATOR(*this);
    BOOST_MULTI_INDEX_CHECK_DECREMENTABLE_ITERATOR(*this);
    --(this->base_reference());
  }

  void advance(difference_type n)
  {
    BOOST_MULTI_INDEX_CHECK_VALID_ITERATOR(*this);
    BOOST_MULTI_INDEX_CHECK_IN_BOUNDS(*this,n);
    this->base_reference()+=n;
  }

  difference_type distance_to(const safe_iterator& x)const
  {
    BOOST_MULTI_INDEX_CHECK_VALID_ITERATOR(*this);
    BOOST_MULTI_INDEX_CHECK_VALID_ITERATOR(x);
    BOOST_MULTI_INDEX_CHECK_SAME_OWNER(*this,x);
    return x.base_reference()-this->base_reference();
  }

#if !defined(BOOST_MULTI_INDEX_DISABLE_SERIALIZATION)
  /* Serialization. Note that Iterator::save and Iterator:load
   * are assumed to be defined and public: at first sight it seems
   * like we could have resorted to the public serialization interface
   * for doing the forwarding to the adapted iterator class:
   *   ar<<base_reference();
   *   ar>>base_reference();
   * but this would cause incompatibilities if a saving
   * program is in safe mode and the loading program is not, or
   * viceversa --in safe mode, the archived iterator data is one layer
   * deeper, this is especially relevant with XML archives.
   * It'd be nice if Boost.Serialization provided some forwarding
   * facility for use by adaptor classes.
   */ 

  friend class boost::serialization::access;

  template<class Archive>
  void serialize(Archive& ar,const unsigned int version)
  {
    core::split_member(ar,*this,version);
  }

  template<class Archive>
  void save(Archive& ar,const unsigned int version)const
  {
    BOOST_MULTI_INDEX_CHECK_VALID_ITERATOR(*this);
    this->base_reference().save(ar,version);
  }

  template<class Archive>
  void load(Archive& ar,const unsigned int version)
  {
    this->base_reference().load(ar,version);
    safe_super::uncheck();
  }
#endif
};

template<typename Iterator>
class safe_container:public safe_mode_detail::safe_container_base
{
  typedef safe_mode_detail::safe_container_base super;

  detail::any_container_view<Iterator> view;

public:
  template<typename Container>
  safe_container(const Container& c):view(c){}

  const void* container()const{return view.container();}
  Iterator    begin()const{return view.begin();}
  Iterator    end()const{return view.end();}

  void detach_dereferenceable_iterators()
  {
    Iterator end_=view.end();
    Iterator *prev_,*next_;
    for(
      prev_=static_cast<Iterator*>(&this->header);
      (next_=static_cast<Iterator*>(prev_->next))!=0;){
      if(*next_!=end_){
        prev_->next=next_->next;
        next_->cont=0;
      }
      else prev_=next_;
    }
  }

  void swap(safe_container<Iterator>& x)
  {
    super::swap(x);
  }
};

/* Invalidates all iterators equivalent to that given. Safe containers
 * must call this when deleting elements: the safe mode framework cannot
 * perform this operation automatically without outside help.
 */

template<typename Iterator>
inline void detach_equivalent_iterators(Iterator& it)
{
  if(it.valid()){
    {
#if defined(BOOST_HAS_THREADS)
      boost::detail::lightweight_mutex::scoped_lock lock(it.cont->mutex);
#endif

      Iterator *prev_,*next_;
      for(
        prev_=static_cast<Iterator*>(&it.cont->header);
        (next_=static_cast<Iterator*>(prev_->next))!=0;){
        if(next_!=&it&&*next_==it){
          prev_->next=next_->next;
          next_->cont=0;
        }
        else prev_=next_;
      }
    }
    it.detach();
  }
}

/* Transfers iterators equivalent to that given to Dst, if that container has
 * the same iterator type; otherwise, detaches them.
 */

template<typename Dst,typename Iterator>
inline void transfer_equivalent_iterators(Dst& dst,Iterator& i)
{
  safe_mode_detail::transfer_equivalent_iterators(
    dst,i,boost::is_same<Iterator,typename Dst::iterator>());
}

namespace safe_mode_detail{

template<typename Dst,typename Iterator>
inline void transfer_equivalent_iterators(
  Dst& dst,Iterator it,boost::true_type /* same iterator type */)
{
  if(it.valid()){
    {
      safe_container_base* cont_=dst.end().cont;

#if defined(BOOST_HAS_THREADS)
      detail::scoped_bilock<boost::detail::lightweight_mutex>
      scoped_bilock(it.cont->mutex,cont_->mutex);
#endif

      Iterator *prev_,*next_;
      for(
        prev_=static_cast<Iterator*>(&it.cont->header);
        (next_=static_cast<Iterator*>(prev_->next))!=0;){
        if(next_!=&it&&*next_==it){
          prev_->next=next_->next;
          next_->cont=cont_;
          next_->next=cont_->header.next;
          cont_->header.next=next_;
        }
        else prev_=next_;
      }
    }
    /* nothing to do with it, was passed by value and will die now */
  }
}

template<typename Dst,typename Iterator>
inline void transfer_equivalent_iterators(
  Dst&,Iterator& it,boost::false_type /* same iterator type */)
{
  detach_equivalent_iterators(it);
}

} /* namespace multi_index::safe_mode::safe_mode_detail */

} /* namespace multi_index::safe_mode */

} /* namespace multi_index */

#if !defined(BOOST_MULTI_INDEX_DISABLE_SERIALIZATION)
namespace serialization{
template<typename Iterator>
struct version<
  boost::multi_index::safe_mode::safe_iterator<Iterator>
>
{
  BOOST_STATIC_CONSTANT(
    int,value=boost::serialization::version<Iterator>::value);
};
} /* namespace serialization */
#endif

} /* namespace boost */

#endif /* BOOST_MULTI_INDEX_ENABLE_SAFE_MODE */

#endif
